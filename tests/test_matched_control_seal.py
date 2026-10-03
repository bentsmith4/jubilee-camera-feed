"""Archive availability and integrity never establish a biological negative."""
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
from seal_matched_control_packet import digest, encoded, fetch_artifact, readback, seal, verify_packet


class SealTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.capture = '2026-10-03T07:26:14.360169-05:00'
        self.prefix = 'archive/2026-10-03/072614'
        self.camera = 'montrose_shoreline'
        self.shots = [{'shot': n, 'timestamp_ct': f'2026-10-03T07:28:{n:02d}-05:00',
                       'timing': 'actual_screenshot_time', 'bytes': len(f'frame{n}'.encode())}
                      for n in (1, 2, 3)]
        files = {'status.json': encoded({'capture_time_ct': self.capture}),
                 'vision.json': encoded({'capture_time_ct': self.capture}),
                 'burst_status.json': encoded({'capture_time_ct': self.capture,
                                              'cameras': {self.camera: {'shots': self.shots}}}),
                 self.camera + '.jpg': b'frame3'}
        self.packet = {'source_commit': 'a' * 40, 'capture_cycle_time_ct': self.capture,
                       'retained_sha256': {n: digest(b) for n, b in files.items()},
                       'primary_camera_id': self.camera,
                       'primary_shots': [{k: s[k] for k in ('timestamp_ct', 'timing', 'shot')} for s in self.shots],
                       'latest_image_sha256': digest(b'frame3'),
                       'sample_classification': 'CANDIDATE_VISIBLE_SCOPE_CONTROL',
                       'tier_a_verified': False, 'whole_morning_outcome': 'UNKNOWN',
                       'biological_event_label': 'unknown', 'clean_training_negative_count': 0,
                       'forecast_predictor_eligible': False, 'search_absence_is_negative': False,
                       'production_action': 'NO_CHANGE'}
        self.files = {**files, 'packet.json': encoded(self.packet)}
        self.raw = self.zip(self.files)
        self.origin = {'id': 123, 'digest': 'sha256:' + digest(self.raw),
                       'workflow_run': {'id': 456, 'head_sha': 'a' * 40}}
        self.objects = {self.prefix + '/' + n: b for n, b in files.items() if n.endswith('.json') and n != 'status.json'}
        local = {n: digest(b) for n, b in files.items()}
        burst = []
        for s in self.shots:
            n = s['shot']
            key = f'{self.prefix}/burst/{self.camera}_{n}.jpg'
            self.objects[key] = f'frame{n}'.encode()
            local[f'burst_latest/{self.camera}_{n}.jpg'] = digest(self.objects[key])
            burst.append({**s, 'archive_key': key})
        self.manifest = {'capture_time_ct': self.capture, 'archive_prefix': self.prefix,
                         'capture_id': '20261003T072614360169-0123456789ab',
                         'cameras': {self.camera: {'ok': True, 'burst': burst}},
                         'local_capture_sha256': local,
                         'sha256': {n: digest(b) for n, b in self.objects.items()}}
        self.refresh_manifest()

    def refresh_manifest(self):
        self.objects[self.prefix + '/manifest.json'] = encoded(self.manifest)

    def zip(self, files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            for name, data in files.items():
                z.writestr(name, data)
        return stream.getvalue()

    def run_seal(self, get=None):
        return seal(self.root, self.raw, self.origin, get or self.objects.__getitem__)

    def assert_bounded(self, path, receipt):
        self.assertFalse(receipt['tier_a_verified'])
        self.assertEqual(receipt['whole_morning_outcome'], 'UNKNOWN')
        self.assertEqual(receipt['clean_training_negative_count'], 0)
        self.assertEqual((path / 'packet/packet.json').read_bytes(), self.files['packet.json'])
        self.assertFalse(json.loads((path / 'packet/packet.json').read_bytes())['tier_a_verified'])

    def test_complete_burst_sealed_and_reopened_without_promotion(self):
        path, receipt = self.run_seal()
        self.assertEqual(receipt['evidence_status'], 'VERIFIED_THREE_FRAME_RETENTION')
        self.assertEqual(readback(path)['readback_status'], 'VERIFIED')
        self.assertEqual(len(list((path / 'r2/burst').glob('*.jpg'))), 3)
        self.assert_bounded(path, receipt)

    def test_missing_manifest_frame_hash_and_failed_readback_are_gaps(self):
        scenarios = ['manifest', 'missing_frame', 'corrupt_frame', 'failed_get']
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                objects = dict(self.objects)
                frame = f'{self.prefix}/burst/{self.camera}_2.jpg'
                if scenario == 'manifest':
                    del objects[self.prefix + '/manifest.json']
                elif scenario == 'missing_frame':
                    del objects[frame]
                elif scenario == 'corrupt_frame':
                    objects[frame] = b'corrupt'
                def get(key):
                    if scenario == 'failed_get':
                        raise OSError('network unavailable')
                    return objects[key]
                path, receipt = self.run_seal(get)
                self.assertEqual(receipt['evidence_status'], 'EVIDENCE_GAP')
                self.assertTrue(receipt['gaps'])
                self.assertFalse((path / 'r2/burst').exists())
                self.assert_bounded(path, receipt)

    def test_wrong_capture_shot_timing_local_hash_and_unstable_manifest(self):
        original = encoded(self.manifest)
        for scenario in ('capture', 'timing', 'hash', 'unstable'):
            self.manifest = json.loads(original)
            if scenario == 'capture':
                self.manifest['capture_time_ct'] = '2026-10-03T07:26:15-05:00'
            elif scenario == 'timing':
                self.manifest['cameras'][self.camera]['burst'][0]['timing'] = 'invented'
            elif scenario == 'hash':
                self.manifest['local_capture_sha256']['status.json'] = '0' * 64
            self.refresh_manifest()
            calls = 0
            def get(key):
                nonlocal calls
                if key.endswith('/manifest.json'):
                    calls += 1
                    if scenario == 'unstable' and calls > 1:
                        return b'changed'
                return self.objects[key]
            path, receipt = self.run_seal(get)
            self.assertEqual(receipt['evidence_status'], 'EVIDENCE_GAP')
            self.assert_bounded(path, receipt)

    def test_missing_or_corrupted_durable_readback_is_gap(self):
        path, receipt = self.run_seal()
        (path / 'r2/burst/montrose_shoreline_1.jpg').write_bytes(b'corrupt')
        self.assertEqual(readback(path)['readback_status'], 'EVIDENCE_GAP')
        (path / 'receipt.json').unlink()
        self.assertEqual(readback(path)['readback_status'], 'EVIDENCE_GAP')
        self.assertEqual(readback(self.root / 'missing')['whole_morning_outcome'], 'UNKNOWN')

    def test_source_gaps_can_be_preserved_without_fabricated_packet(self):
        for gap in ('ARTIFACT_EXPIRED', 'ARTIFACT_MISSING', 'ARTIFACT_FAILED_READBACK'):
            path, receipt = seal(self.root, None, self.origin, None, gap)
            self.assertEqual(receipt['evidence_status'], 'EVIDENCE_GAP')
            self.assertIsNone(receipt['packet_sha256'])
            self.assertEqual(readback(path)['whole_morning_outcome'], 'UNKNOWN')

    def test_expired_identity_and_digest_artifacts_rejected_before_admission(self):
        now = datetime.now(timezone.utc)
        metadata = {**self.origin, 'name': 'fixture', 'expired': False,
                    'created_at': now.isoformat(), 'expires_at': (now + timedelta(days=1)).isoformat()}
        def get(url, token):
            return self.raw if url.endswith('/zip') else encoded(metadata)
        raw, origin = fetch_artifact('owner/repo', 123, 456, 'a' * 40, None, get)
        self.assertEqual(raw, self.raw)
        for mutate in (lambda: metadata.update(expired=True),
                       lambda: metadata.update(expired=False, expires_at=(now - timedelta(days=1)).isoformat()),
                       lambda: metadata.update(expires_at=(now + timedelta(days=1)).isoformat(), digest='sha256:' + '0' * 64),
                       lambda: metadata.update(id=124)):
            mutate()
            with self.assertRaises(ValueError):
                fetch_artifact('owner/repo', 123, 456, 'a' * 40, None, get)

    def test_packet_tampering_and_path_traversal_rejected(self):
        for changed in ({**self.files, 'status.json': b'corrupt'}, {**self.files, '../escape': b'x'}):
            raw = self.zip(changed)
            with self.assertRaises(ValueError):
                verify_packet(raw, {**self.origin, 'digest': 'sha256:' + digest(raw)})


if __name__ == '__main__':
    unittest.main()

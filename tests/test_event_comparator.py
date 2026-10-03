"""Prospective positive evidence cannot bypass identity, geometry or UNKNOWN."""
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
from collect_event_comparator import enrich, PROTOCOL
from seal_matched_control_packet import digest, encoded, verify_packet, seal, readback
from test_matched_control_seal import SealTests


class EventComparatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SealTests('test_complete_burst_sealed_and_reopened_without_promotion')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.repo = f.root / 'repo'
        self.out = f.root / 'packet'
        self.repo.mkdir()
        self.out.mkdir()
        target = self.repo / PROTOCOL
        target.parent.mkdir()
        target.write_bytes((Path(__file__).resolve().parents[1] / PROTOCOL).read_bytes())
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=test',
                        '-c', 'user.email=test@example.com', 'commit', '-qm', 'design'], check=True)
        for name, raw in f.files.items():
            (self.out / name).write_bytes(raw)

    def archive(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            for p in self.out.rglob('*'):
                if p.is_file():
                    z.writestr(p.relative_to(self.out).as_posix(), p.read_bytes())
        raw = stream.getvalue()
        return raw, {**self.fixture.origin, 'digest': 'sha256:' + digest(raw)}

    def test_complete_event_candidate_reopens_and_existing_sealer_accepts(self):
        p = enrich(self.repo, self.out, self.fixture.objects.__getitem__)
        self.assertEqual(p['event_comparator']['burst_retention'], 'VERIFIED_THREE_FRAME_RETENTION')
        self.assertEqual((self.out / 'original-packet.json').read_bytes(), self.fixture.files['packet.json'])
        self.assertEqual(len(list((self.out / 'r2/burst').glob('*.jpg'))), 3)
        review = json.loads((self.out / 'event-review-template.json').read_bytes())
        self.assertEqual(len(review['matching_evidence']), 8)
        self.assertEqual(review['biological_event_label'], 'unknown')
        self.assertEqual(review['geometry_review'], 'NOT_PERFORMED')
        raw, origin = self.archive()
        verify_packet(raw, origin)
        directory, receipt = seal(self.fixture.root / 'sealed', raw, origin, self.fixture.objects.__getitem__)
        self.assertEqual(readback(directory)['readback_status'], 'VERIFIED')
        self.assertFalse(receipt['tier_a_verified'])
        self.assertEqual(receipt['whole_morning_outcome'], 'UNKNOWN')
        with self.assertRaises(ValueError):
            enrich(self.repo, self.out, self.fixture.objects.__getitem__)

    def test_missing_corrupt_or_wrong_capture_remains_gap_without_partial_burst(self):
        for scenario in ('missing', 'corrupt', 'wrong_capture'):
            with self.subTest(scenario=scenario):
                objects = dict(self.fixture.objects)
                key = self.fixture.prefix + '/burst/montrose_shoreline_2.jpg'
                if scenario == 'missing':
                    del objects[key]
                elif scenario == 'corrupt':
                    objects[key] = b'bad'
                else:
                    manifest = deepcopy(self.fixture.manifest)
                    manifest['capture_time_ct'] = '2026-10-04T07:26:14-05:00'
                    objects[self.fixture.prefix + '/manifest.json'] = encoded(manifest)
                # Fresh packet for each scenario.
                out = self.fixture.root / scenario
                out.mkdir()
                for name, raw in self.fixture.files.items():
                    (out / name).write_bytes(raw)
                p = enrich(self.repo, out, objects.__getitem__)
                self.assertEqual(p['event_comparator']['burst_retention'], 'EVIDENCE_GAP')
                self.assertFalse((out / 'r2').exists())
                self.assertFalse(p['tier_a_verified'])
                self.assertEqual(p['whole_morning_outcome'], 'UNKNOWN')

    def test_dirty_design_and_corrupt_packet_rejected(self):
        path = self.repo / PROTOCOL
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'protocol differs'):
            enrich(self.repo, self.out, self.fixture.objects.__getitem__)
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '--', PROTOCOL], check=True)
        (self.out / 'status.json').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            enrich(self.repo, self.out, self.fixture.objects.__getitem__)

    def test_event_signal_does_not_change_collection_or_assign_label(self):
        packet_path = self.out / 'packet.json'
        p = json.loads(packet_path.read_bytes())
        p['sample_classification'] = 'UNKNOWN_OR_EVENT_REVIEW_REQUIRED'
        packet_path.write_bytes(encoded(p))
        p = enrich(self.repo, self.out, self.fixture.objects.__getitem__)
        self.assertEqual(p['event_comparator']['burst_retention'], 'VERIFIED_THREE_FRAME_RETENTION')
        self.assertEqual(p['biological_event_label'], 'unknown')
        self.assertFalse(p['forecast_predictor_eligible'])
        self.assertEqual(p['clean_training_negative_count'], 0)


if __name__ == '__main__':
    unittest.main()

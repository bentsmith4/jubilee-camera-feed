"""Offline acceptance fixtures use real JPEGs, freeze(), and local Git history."""
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import desktop_verify as v
import archive_integrity


class ReadOnlyR2:
    def __init__(self, objects):
        self.objects = objects
        self.calls = []
        self.bodies = []

    def get_object(self, *, Bucket, Key):
        self.calls.append(Key)
        body = io.BytesIO(self.objects[Key])
        self.bodies.append(body)
        return {'Body': body}


class Fixture:
    def __init__(self, root):
        self.root = root
        self.now = datetime(2026, 9, 27, 12, 10, tzinfo=timezone.utc)
        self.capture = self.now - timedelta(minutes=4)
        self.frames = root / 'frames'
        self.frames.mkdir()
        self.docs = {name: {'capture_time_ct': self.capture.isoformat(), 'cameras': {}} for name in v.METADATA}
        real_schema = json.loads((Path(__file__).parent / 'fixtures' / 'desktop_shot_metadata.json').read_text())
        for camera in v.CAMERA_IDS:
            shots = copy.deepcopy(real_schema['shots'])
            vision_shots = copy.deepcopy(real_schema['burst_shots'])
            for n in (1, 2, 3):
                output = io.BytesIO()
                v.Image.new('RGB', (10, 10), (n * 50, 20, 30)).save(output, format='JPEG')
                content = output.getvalue()
                name = f'burst_latest/{camera}_{n}.jpg'
                self.write(name, content)
                for records in (shots, vision_shots):
                    records[n - 1].update(timestamp_ct=(self.capture + timedelta(seconds=n * 10)).isoformat(),
                                          bytes=len(content), file=Path(name).name)
            self.write(camera + '.jpg', content)
            self.docs['status.json']['cameras'][camera] = dict(ok=True, timestamp_ct=shots[-1]['timestamp_ct'], bytes=len(content), burst_count=3)
            self.docs['burst_status.json']['cameras'][camera] = dict(ok=True, shots=shots)
            self.docs['vision.json']['cameras'][camera] = dict(status='ok', burst_frame_count=3,
                burst_shots=vision_shots)
        self.save()
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 9, 27, 12, 10, tzinfo=timezone.utc)
        with patch.object(archive_integrity, 'datetime', Clock):
            self.folder, self.seal = archive_integrity.freeze(root)
        self.inventory = dict(available=True, tasks=[dict(role='coordinator', enabled=True,
            state='Running', action_matches=True, last_result=0x41301, missed_runs=0,
            last_run=(self.now - timedelta(days=5)).isoformat()),
            dict(role='additional_capture_task', state='Disabled', enabled=False)])
        state = dict(heartbeat=self.now.isoformat(), last_live_success=self.now.isoformat(),
                     last_canonical_success=self.now.isoformat(), canonical_monitoring_status='completed')
        (root / 'capture_service_state.json').write_text(json.dumps(state))
        live = root / 'live_frames'
        live.mkdir()
        (live / 'status.json').write_text(json.dumps(self.docs['status.json']))
        for cam in v.CAMERA_IDS:
            (live / (cam + '.jpg')).write_bytes((self.frames / (cam + '.jpg')).read_bytes())
        self.repo = root / 'jubilee-camera-feed'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Acceptance Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        (self.repo / 'model.py').write_text('untouched model\n')
        self.git('add', '.')
        self.git('commit', '-m', 'previous main')
        self.previous = self.git('rev-parse', 'HEAD').decode().strip()
        for name in v.METADATA + tuple(cam + '.jpg' for cam in v.CAMERA_IDS):
            (self.repo / name).write_bytes((self.frames / name).read_bytes())
        self.git('add', '.')
        self.git('commit', '-m', 'Latest Jubilee camera burst')
        self.published = self.git('rev-parse', 'HEAD').decode().strip()
        (self.repo / '.git' / 'FETCH_HEAD').write_text(self.previous + "\t\tbranch 'main' of https://github.com/bentsmith4/jubilee-camera-feed\n")
        (root / 'capture_service.log').write_text('private diagnostics not for output\nGITHUB APPEND-ONLY PUBLISH SUCCESS: ' + self.published + '\n')
        self.manifest, self.objects = self.archive_objects()
        self.client = ReadOnlyR2(self.objects)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True).stdout

    def write(self, name, content):
        path = self.frames / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def save(self):
        for name, doc in self.docs.items():
            self.write(name, json.dumps(doc).encode())

    def archive_objects(self):
        prefix = self.capture.strftime('archive/%Y-%m-%d/%H%M%S')
        objects = {}
        cameras = {}
        for camera in v.CAMERA_IDS:
            source = self.docs['status.json']['cameras'][camera]
            cameras[camera] = {key: source[key] for key in ('ok', 'timestamp_ct', 'bytes')}
            cameras[camera].update(latest_key=camera + '.jpg', burst=[])
            objects[camera + '.jpg'] = (self.frames / (camera + '.jpg')).read_bytes()
            for original in self.docs['burst_status.json']['cameras'][camera]['shots']:
                name = f'{camera}_{original["shot"]}.jpg'
                key = prefix + '/burst/' + name
                shot = {k: original[k] for k in ('shot', 'timestamp_ct', 'timing', 'bytes')}
                shot['archive_key'] = key
                cameras[camera]['burst'].append(shot)
                objects[key] = (self.frames / 'burst_latest' / name).read_bytes()
        for name in ('vision.json', 'burst_status.json'):
            objects[name] = (self.frames / name).read_bytes()
            objects[prefix + '/' + name] = objects[name]
        manifest = dict(capture_id=self.seal['capture_id'], capture_time_ct=self.capture.isoformat(),
            archive_prefix=prefix, local_capture_sha256=self.seal['sha256'],
            sha256={key: v.digest(content) for key, content in objects.items()}, cameras=cameras)
        raw = json.dumps(manifest).encode()
        objects[prefix + '/manifest.json'] = raw
        objects['archive/latest_manifest.json'] = raw
        objects['status.json'] = (self.frames / 'status.json').read_bytes()
        return manifest, objects

    def snapshot(self):
        snap = v.Snapshot(self.root)
        snap.load(self.now)
        for camera in v.CAMERA_IDS:
            snap.camera(camera, self.now)
        snap.archive()
        return snap

    def verify(self, **kwargs):
        with patch.object(v, 'remote_tip', return_value=self.published):
            return v.verify(self.root, self.inventory, now=self.now,
                client_factory=lambda root: (self.client, 'private-bucket'), **kwargs)


def fingerprints(root):
    return {str(p.relative_to(root)): v.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


class VerifierTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.f = Fixture(Path(temp.name))

    def test_complete_read_only_acceptance_and_closed_get_bodies(self):
        # Dirty/staged work and the entire Git directory must remain byte-identical.
        (self.f.repo / 'model.py').write_text('staged private model work')
        self.f.git('add', 'model.py')
        (self.f.repo / 'untracked.txt').write_text('untracked')
        before = fingerprints(self.f.root)
        report = self.f.verify()
        self.assertEqual(report['status'], 'PASS', report)
        self.assertEqual(len(report['cameras']), 6)
        self.assertEqual(report['checks']['local_archive']['objects_verified'], 27)
        self.assertEqual(report['checks']['r2_archive']['objects_verified'], 30)
        self.assertEqual(len(self.f.client.calls), 32)
        self.assertTrue(all(body.closed for body in self.f.client.bodies))
        self.assertEqual(fingerprints(self.f.root), before)

    def test_missing_credentials_is_not_verified(self):
        report = v.checked(v.r2_archive, self.f.root, self.f.snapshot())
        self.assertEqual(report['status'], 'NOT_VERIFIED')
        self.assertEqual(report['code'], 'r2_credentials_unavailable')

    def test_offline_never_calls_network_or_credentials(self):
        with patch.object(v, 'remote_tip', side_effect=AssertionError('network')), \
                patch.object(v, 'github_compare', side_effect=AssertionError('network')):
            report = v.verify(self.f.root, self.f.inventory, now=self.f.now, offline=True,
                client_factory=lambda root: self.fail('credentials accessed'))
        self.assertEqual(report['status'], 'NOT_VERIFIED')
        self.assertEqual(report['checks']['git_publication']['local_contract'], 'PASS')
        self.assertEqual(self.f.client.calls, [])

    def test_task_health_running_code_and_disabled_legacy_allowed(self):
        self.assertEqual(v.checked(v.task_health, self.f.root, self.f.inventory, self.f.now)['status'], 'PASS')
        for change in ({'state': 'Ready'}, {'last_result': 1}, {'missed_runs': 1}, {'action_matches': False}, {'enabled': False}):
            inv = copy.deepcopy(self.f.inventory)
            inv['tasks'][0].update(change)
            self.assertEqual(v.checked(v.task_health, self.f.root, inv, self.f.now)['status'], 'FAIL', change)
        inv = copy.deepcopy(self.f.inventory)
        inv['tasks'][1].update(enabled=True, state='Ready')
        self.assertEqual(v.checked(v.task_health, self.f.root, inv, self.f.now)['code'], 'additional_capture_task_enabled')
        self.assertEqual(v.checked(v.task_health, self.f.root, None, self.f.now)['status'], 'NOT_VERIFIED')

    def test_stale_heartbeat_not_running_health(self):
        path = self.f.root / 'capture_service_state.json'
        state = json.loads(path.read_text())
        state['heartbeat'] = (self.f.now - timedelta(minutes=26)).isoformat()
        path.write_text(json.dumps(state))
        self.assertEqual(self.f.verify()['checks']['scheduled_tasks']['status'], 'FAIL')

    def test_metadata_mismatch_missing_camera_and_timestamps(self):
        original = copy.deepcopy(self.f.docs)
        for mutate in (
            lambda d: d['vision.json'].update(capture_time_ct='2026-09-27T11:00:00+00:00'),
            lambda d: d['status.json']['cameras'].pop(v.CAMERA_IDS[-1]),
            lambda d: d['burst_status.json'].update(capture_id='different'),
            lambda d: [doc.update(capture_time_ct='2026-09-27T12:06:00') for doc in d.values()],
            lambda d: [doc.update(capture_time_ct='2026-09-27T10:00:00+00:00') for doc in d.values()],
            lambda d: [doc.update(capture_time_ct='2026-09-27T13:00:00+00:00') for doc in d.values()],
        ):
            self.f.docs = copy.deepcopy(original)
            mutate(self.f.docs)
            self.f.save()
            self.assertEqual(v.checked(v.Snapshot(self.f.root).load, self.f.now)['status'], 'FAIL')

    def test_all_six_results_are_reported_even_when_one_fails(self):
        self.f.docs['status.json']['cameras'][v.CAMERA_IDS[0]]['ok'] = False
        self.f.save()
        report = self.f.verify()
        self.assertEqual(sum(row['status'] == 'PASS' for row in report['cameras'].values()), 5)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['checks']['local_archive']['status'], 'NOT_VERIFIED')

    def test_incomplete_burst_failed_vision_and_wrong_vision_shots(self):
        camera = v.CAMERA_IDS[0]
        original = copy.deepcopy(self.f.docs)
        for mutate in (
            lambda d: d['burst_status.json']['cameras'][camera]['shots'].pop(),
            lambda d: d['vision.json']['cameras'][camera].update(status='burst_not_ok'),
            lambda d: d['vision.json']['cameras'][camera]['burst_shots'][0].update(timestamp_ct='wrong'),
            lambda d: d['status.json']['cameras'][camera].update(timestamp_ct=self.f.capture.isoformat()),
        ):
            self.f.docs = copy.deepcopy(original)
            mutate(self.f.docs)
            self.f.save()
            snap = v.Snapshot(self.f.root)
            snap.load(self.f.now)
            self.assertEqual(v.checked(snap.camera, camera, self.f.now)['status'], 'FAIL')

    def test_real_schema_has_full_independent_shot_records(self):
        camera = v.CAMERA_IDS[0]
        burst = self.f.docs['burst_status.json']['cameras'][camera]['shots']
        vision = self.f.docs['vision.json']['cameras'][camera]['burst_shots']
        self.assertEqual(vision, burst)
        self.assertIsNot(vision[0], burst[0])
        self.assertEqual(set(vision[0]), {'shot', 'timestamp_ct', 'file', 'bytes', 'timing'})
        self.assertEqual(self.f.verify()['status'], 'PASS')

    def test_vision_file_and_bytes_must_match_burst(self):
        camera = v.CAMERA_IDS[0]
        original = copy.deepcopy(self.f.docs)
        for field, value in (('file', 'other_camera_1.jpg'), ('bytes', 1)):
            with self.subTest(field=field):
                self.f.docs = copy.deepcopy(original)
                self.f.docs['vision.json']['cameras'][camera]['burst_shots'][0][field] = value
                self.f.save()
                report = self.f.verify()
                self.assertEqual(report['cameras'][camera],
                                 v.result('FAIL', 'vision_shot_identity_mismatch'))

    def test_agreeing_metadata_still_requires_correct_file_and_actual_bytes(self):
        camera = v.CAMERA_IDS[0]
        original = copy.deepcopy(self.f.docs)
        for field, value, code in (('file', '../other.jpg', 'shot_file_identity_mismatch'),
                                   ('bytes', 1, 'shot_size_mismatch'),
                                   ('bytes', True, 'shot_size_mismatch')):
            with self.subTest(field=field, value=value):
                self.f.docs = copy.deepcopy(original)
                for name, key in (('burst_status.json', 'shots'), ('vision.json', 'burst_shots')):
                    self.f.docs[name]['cameras'][camera][key][0][field] = value
                self.f.save()
                self.assertEqual(self.f.verify()['cameras'][camera], v.result('FAIL', code))

    def live_refresh_fixture(self, changed_product=None):
        # Deterministic interleaving: read old status, read an image from the next
        # refresh (wrong size), then advance status or image before the recheck.
        camera = v.CAMERA_IDS[0]
        image = self.f.root / 'live_frames' / (camera + '.jpg')
        image.write_bytes(image.read_bytes() + b'next refresh')
        read = v.read_file
        fired = False

        def interleaved(root, relative):
            nonlocal fired
            content = read(root, relative)
            if relative == 'live_frames/' + camera + '.jpg' and not fired:
                fired = True
                if changed_product == 'status':
                    path = self.f.root / 'live_frames' / 'status.json'
                    doc = json.loads(path.read_text())
                    doc['cameras'][camera]['bytes'] = len(content)
                    path.write_text(json.dumps(doc))
                elif changed_product == 'image':
                    image.write_bytes(content + b'changed again')
            return content
        return patch.object(v, 'read_file', side_effect=interleaved)

    def test_stable_live_size_failure_remains_fail(self):
        with self.live_refresh_fixture():
            self.assertEqual(v.checked(v.live_health, self.f.root, self.f.now),
                             v.result('FAIL', 'live_size_mismatch'))

    def test_failed_live_check_rechecks_both_status_and_image(self):
        for changed_product in ('status', 'image'):
            with self.subTest(changed_product=changed_product):
                with self.live_refresh_fixture(changed_product):
                    self.assertEqual(v.checked(v.live_health, self.f.root, self.f.now),
                                     v.result('NOT_VERIFIED', 'live_changed_during_check'))

    def test_stable_live_jpeg_failure_remains_fail(self):
        camera = v.CAMERA_IDS[0]
        path = self.f.root / 'live_frames' / (camera + '.jpg')
        path.write_bytes(b'x' * len(path.read_bytes()))
        self.assertEqual(v.checked(v.live_health, self.f.root, self.f.now),
                         v.result('FAIL', 'invalid_jpeg'))

    def test_live_race_does_not_clear_real_pointclear_failures(self):
        failed = ('pcl_e2_back_deck', 'pcl_e3_bay_mouth')
        for camera in failed:
            self.f.docs['status.json']['cameras'][camera]['ok'] = False
            self.f.docs['burst_status.json']['cameras'][camera]['ok'] = False
            self.f.docs['vision.json']['cameras'][camera]['status'] = 'burst_not_ok'
        self.f.save()
        with self.live_refresh_fixture('status'):
            report = self.f.verify()
        self.assertEqual(report['checks']['near_live']['status'], 'NOT_VERIFIED')
        self.assertEqual(report['status'], 'FAIL')
        for camera in v.CAMERA_IDS:
            self.assertEqual(report['cameras'][camera]['status'], 'FAIL' if camera in failed else 'PASS')
        for check in ('local_archive', 'git_publication', 'r2_archive'):
            self.assertEqual(report['checks'][check]['status'], 'NOT_VERIFIED')
        self.assertEqual(self.f.client.calls, [])

    def test_corrupt_jpeg_and_latest_not_shot_three(self):
        camera = v.CAMERA_IDS[0]
        snap = v.Snapshot(self.f.root)
        snap.load(self.f.now)
        self.f.write(camera + '.jpg', b'not jpeg')
        self.assertNotEqual(v.checked(snap.camera, camera, self.f.now)['status'], 'PASS')
        self.f.write(camera + '.jpg', (self.f.frames / f'burst_latest/{camera}_1.jpg').read_bytes())
        self.assertEqual(v.checked(snap.camera, camera, self.f.now)['status'], 'FAIL')

    def test_local_manifest_requires_complete_original_hashes(self):
        snap = self.f.snapshot()
        path = self.f.folder / 'capture_manifest.json'
        seal = json.loads(path.read_text())
        seal['sha256'].pop('status.json')
        path.write_text(json.dumps(seal))
        self.assertEqual(v.checked(snap.archive)['code'], 'local_manifest_hash_set_mismatch')

    def test_local_archive_tampering(self):
        snap = self.f.snapshot()
        (self.f.folder / 'vision.json').write_bytes(b'corrupt')
        self.assertEqual(v.checked(snap.archive)['code'], 'local_archive_hash_mismatch')

    def test_local_and_remote_hashless_manifests_are_unverified(self):
        snap = self.f.snapshot()
        seal = dict(self.f.seal)
        seal.pop('sha256')
        (self.f.folder / 'capture_manifest.json').write_text(json.dumps(seal))
        self.assertEqual(v.checked(snap.archive)['status'], 'NOT_VERIFIED')
        self.f.manifest.pop('sha256')
        self.f.objects['archive/latest_manifest.json'] = json.dumps(self.f.manifest).encode()
        value = v.checked(v.r2_archive, self.f.root, snap, client_factory=lambda root: (self.f.client, 'bucket'))
        self.assertEqual(value['code'], 'r2_original_hashes_missing')

    def test_missing_local_archive_is_unverified(self):
        (self.f.folder / 'capture_manifest.json').unlink()
        self.assertEqual(self.f.verify()['checks']['local_archive']['status'], 'NOT_VERIFIED')

    def test_freshness_boundaries(self):
        for offset, passes in ((60, True), (60.01, False), (-2, True), (-2.01, False)):
            value = (self.f.now - timedelta(minutes=offset)).isoformat()
            if passes:
                self.assertEqual(v.fresh(value, self.f.now, 60), v.timestamp(value))
            else:
                with self.assertRaises(v.EvidenceError):
                    v.fresh(value, self.f.now, 60)

    def test_no_traversal_or_symlink_escape_reads(self):
        self.assertEqual(v.checked(v.read_file, self.f.root, '../outside')['code'], 'path_outside_evidence_root')
        with tempfile.TemporaryDirectory() as outside:
            link = self.f.frames / 'escape'
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest('OS disallows symlink fixture')
            self.assertEqual(v.checked(v.read_file, self.f.root, 'frames/escape/file')['code'], 'path_outside_evidence_root')

    def test_missing_snapshot_and_malformed_json_never_pass(self):
        self.f.write('status.json', b'{broken')
        report = self.f.verify()
        self.assertNotEqual(report['status'], 'PASS')
        self.assertEqual(len(report['cameras']), 6)

    def test_capture_race_invalidates_acceptance(self):
        original = v.publication
        def race(*args, **kwargs):
            value = original(*args, **kwargs)
            self.f.write('status.json', b'{}')
            return value
        with patch.object(v, 'publication', side_effect=race):
            report = self.f.verify()
        self.assertEqual(report['status'], 'NOT_VERIFIED')
        self.assertEqual(report['checks']['snapshot_stability']['code'], 'capture_changed_during_check')

    def test_r2_corruption_and_historical_hashless_manifest(self):
        snap = self.f.snapshot()
        key = next(k for k in self.f.objects if '/burst/' in k)
        self.f.objects[key] = b'corrupted'
        value = v.checked(v.r2_archive, self.f.root, snap, client_factory=lambda root: (self.f.client, 'bucket'))
        self.assertEqual(value['code'], 'r2_readback_hash_mismatch')
        self.f.objects['archive/latest_manifest.json'] = b'{"capture_time_ct":"old"}'
        value = v.checked(v.r2_archive, self.f.root, snap, client_factory=lambda root: (self.f.client, 'bucket'))
        self.assertEqual(value['status'], 'FAIL')

    def test_r2_pointer_race_is_inconclusive(self):
        old = self.f.client.get_object
        count = 0
        def race(**kw):
            nonlocal count
            if kw['Key'] == 'archive/latest_manifest.json':
                count += 1
                if count == 2:
                    return {'Body': io.BytesIO(b'new capture')}
            return old(**kw)
        self.f.client.get_object = race
        self.assertEqual(self.f.verify()['checks']['r2_archive']['code'], 'r2_pointer_changed_during_check')

    def test_r2_manifest_cannot_request_arbitrary_keys(self):
        self.f.manifest['sha256']['../secret'] = '0' * 64
        self.f.objects['archive/latest_manifest.json'] = json.dumps(self.f.manifest).encode()
        report = self.f.verify()
        self.assertEqual(report['checks']['r2_archive']['code'], 'r2_object_hash_set_mismatch')
        self.assertNotIn('../secret', self.f.client.calls)

    def test_git_rejects_model_change_merge_and_wrong_parent(self):
        snap = self.f.snapshot()
        (self.f.repo / 'model.py').write_text('unexpected model change')
        self.f.git('add', '.')
        self.f.git('commit', '--amend', '--no-edit')  # Fixture only; verifier never amends.
        commit = self.f.git('rev-parse', 'HEAD').decode().strip()
        value = v.checked(v.publication, self.f.root, snap, commit, self.f.previous, True)
        self.assertEqual(value['code'], 'publication_changed_nonallowlisted_paths')
        value = v.checked(v.publication, self.f.root, snap, self.f.published, commit, True)
        self.assertEqual(value['code'], 'prior_main_not_publication_parent')
        tree = self.f.git('rev-parse', 'HEAD^{tree}').decode().strip()
        merge = self.f.git('commit-tree', tree, '-p', commit, '-p', self.f.published, '-m', 'merge fixture').decode().strip()
        self.assertEqual(v.checked(v.publication, self.f.root, snap, merge, commit, True)['code'], 'publication_not_single_parent')

    def test_git_missing_receipt_objects_and_remote_divergence(self):
        snap = self.f.snapshot()
        (self.f.root / 'capture_service.log').write_text('no receipt')
        self.assertEqual(v.checked(v.publication, self.f.root, snap)['status'], 'NOT_VERIFIED')
        with patch.object(v, 'remote_tip', return_value='a' * 40), \
                patch.object(v, 'github_compare', side_effect=v.EvidenceError('NOT_VERIFIED', 'github_ancestry_unavailable')):
            value = v.checked(v.publication, self.f.root, snap, self.f.published, self.f.previous)
        self.assertEqual(value['status'], 'NOT_VERIFIED')
        with patch.object(v, 'remote_tip', return_value=self.f.previous):
            value = v.checked(v.publication, self.f.root, snap, self.f.published, self.f.previous)
        self.assertEqual(value['code'], 'publication_not_on_current_main')

    def test_git_allows_later_unrelated_main_commits(self):
        snap = self.f.snapshot()
        (self.f.repo / 'model.py').write_text('later legitimate model change')
        self.f.git('add', '.')
        self.f.git('commit', '-m', 'later unrelated update')
        tip = self.f.git('rev-parse', 'HEAD').decode().strip()
        with patch.object(v, 'remote_tip', return_value=tip):
            value = v.checked(v.publication, self.f.root, snap)
        self.assertEqual(value['status'], 'PASS')

    def test_partial_clone_refused_before_object_reads(self):
        snap = self.f.snapshot()
        self.f.git('config', 'remote.origin.promisor', 'true')
        before = fingerprints(self.f.root)
        value = v.checked(v.publication, self.f.root, snap)
        self.assertEqual(value['code'], 'partial_clone_requires_existing_full_history')
        self.assertEqual(fingerprints(self.f.root), before)

    def test_replaced_fetch_head_is_missing_evidence_not_failed_ancestry(self):
        snap = self.f.snapshot()
        path = self.f.repo / '.git' / 'FETCH_HEAD'
        path.write_text(self.f.published + "\t\tbranch 'main' of remote\n")
        value = v.checked(v.publication, self.f.root, snap)
        self.assertEqual(value['status'], 'NOT_VERIFIED')

    def test_remote_movement_is_unverified(self):
        snap = self.f.snapshot()
        with patch.object(v, 'remote_tip', side_effect=[self.f.published, self.f.previous]):
            value = v.checked(v.publication, self.f.root, snap)
        self.assertEqual(value['code'], 'remote_main_changed_during_check')

    def test_r2_endpoint_rejected_without_leaking_configuration(self):
        (self.f.root / 'r2.json').write_text(json.dumps(dict(endpoint='http://secret.invalid',
            access_key='SENTINEL_ACCESS', secret_key='SENTINEL_SECRET')))
        value = v.checked(v.r2_client, self.f.root)
        self.assertEqual(value, v.result('NOT_VERIFIED', 'r2_endpoint_invalid'))

    def test_sentinel_secrets_never_appear_in_report_or_cli(self):
        secret = 'SENTINEL_SECRET_BEARER_rtsp://private'
        self.f.docs['status.json']['error'] = secret
        self.f.save()
        self.f.inventory['tasks'][0]['arguments'] = secret
        self.f.inventory['tasks'][0]['state'] = secret
        self.f.client.get_object = lambda **kw: (_ for _ in ()).throw(RuntimeError(secret))
        report = self.f.verify()
        self.assertNotIn(secret, json.dumps(report))
        command = [sys.executable, '-B', str(Path(v.__file__)), '--root', str(self.f.root), '--tasks-stdin', '--offline']
        proc = subprocess.run(command, input=json.dumps(self.f.inventory), capture_output=True, text=True)
        self.assertIn(proc.returncode, (1, 2))
        self.assertEqual(proc.stderr, '')
        self.assertNotIn(secret, proc.stdout)
        json.loads(proc.stdout)

    def test_r2_sdk_error_is_sanitized(self):
        def unavailable(root):
            raise RuntimeError('https://endpoint?secret=SUPERSECRET')
        report = v.checked(v.r2_archive, self.f.root, self.f.snapshot(), client_factory=unavailable)
        self.assertEqual(report, v.result('NOT_VERIFIED', 'evidence_unavailable'))


if __name__ == '__main__':
    unittest.main()

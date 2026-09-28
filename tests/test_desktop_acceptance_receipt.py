"""Real Git histories exercise receipt binding, expiry and scientific isolation."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
import desktop_acceptance as receipt
import reconcile_current_state as builder
import test_current_state_reconciliation as fixture

T0 = fixture.T0


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.b = fixture.ReconciliationTests('test_dirty_and_unpublished_files_cannot_enter_state')
        self.b.setUp()
        self.addCleanup(self.b.doCleanups)
        self.root, self.f = self.b.root, self.b.f
        registry = self.f.read('model_data/camera_sources.json')
        self.mapping = dict(zip(sorted(c['camera_id'] for c in registry['cameras']), receipt.CAMERAS))
        for c in registry['cameras']:
            c['camera_id'] = self.mapping[c['camera_id']]
        self.f.write('model_data/camera_sources.json', registry)
        self.f.write(receipt.SOURCE, b'# reviewed source fixture\n')
        parent = self.b.commit('reviewed source and registry')
        for path in receipt.METADATA:
            doc = self.f.read(path)
            doc['cameras'] = {self.mapping[k]: v for k, v in doc['cameras'].items()}
            for cid, value in doc['cameras'].items():
                for shot in value.get('shots', value.get('burst_shots', [])):
                    shot['file'] = cid + '_' + str(shot['shot']) + '.jpg'
            self.f.write(path, doc)
        for old, new in self.mapping.items():
            self.f.write(new+'.jpg', (self.root/(old+'.jpg')).read_bytes())
        pub = self.b.commit('accepted camera publication')
        self.f.write('review.txt', b'reviewed without changing capture')
        reviewed = self.b.commit('reviewed main')
        self.baseline = json.loads(builder.build(self.root, T0)[0])

        self.r = json.loads((ROOT / receipt.RECEIPT).read_bytes())
        self.report = json.loads((ROOT / self.r['provenance']['verifier_report']['path']).read_bytes())
        capture = T0 - timedelta(minutes=5)
        self.report['checked_at_utc'] = (T0 - timedelta(minutes=1)).isoformat()
        checks = self.report['checks']
        checks['capture']['capture_time_utc'] = capture.isoformat()
        checks['local_archive']['capture_id'] = capture.strftime('%Y%m%dT%H%M%S%f') + '-0123456789ab'
        checks['git_publication'].update(published_commit=pub, previous_main=parent, current_main=reviewed, changed_path_count=9)
        self.r['execution_window'].update(started_at=(T0-timedelta(minutes=2)).isoformat(), completed_at=(T0-timedelta(seconds=30)).isoformat())
        source_hash = builder.guard.digest((self.root/receipt.SOURCE).read_bytes())
        self.r['deployment'].update(reviewed_main_commit=reviewed, pr_head_commit=parent,
            source_sha256=source_hash, deployed_sha256=source_hash,
            required_ancestors=dict(cadence=parent, forecast_contract=parent))
        self.r['publication_changed_paths'] = sorted(receipt.FILES)
        self.r['published_files'] = {p:dict(sha256=builder.guard.digest((self.root/p).read_bytes()),
            git_blob=self.f.git('rev-parse', pub+':'+p)) for p in receipt.FILES}
        c = self.r['provenance']['issue_comment']
        c.update(created_at=T0.isoformat(), updated_at=T0.isoformat())
        body = 'Final status: PASS\n' + '\n'.join((reviewed, parent, pub, source_hash,
            self.r['deployment']['pr_url'], checks['local_archive']['capture_id'], capture.isoformat(),
            *receipt.CAMERAS, 'all 27 objects', '30 objects', '18 immutable burst frames',
            'GET/hash/decode', 'GIT_ALTERNATE_OBJECT_DIRECTORIES')) + '\n'
        self.f.write(c['path'], body.encode())
        c['sha256'] = builder.guard.digest(body.encode())
        self.save_report()
        self.save()

    def save_report(self):
        ref = self.r['provenance']['verifier_report']
        self.f.write(ref['path'], self.report)
        ref['sha256'] = builder.guard.digest((self.root/ref['path']).read_bytes())

    def save(self):
        self.f.write(receipt.RECEIPT, self.r)
        self.b.commit('receipt evidence')

    def consume(self, now=T0):
        return receipt.consume(builder.CommittedReader(self.root), now, 60)

    def assert_ignored(self, result, code):
        self.assertEqual(result['status'], 'NOT_VERIFIED')
        self.assertIn(code, result['reason_codes'])

    def test_valid_receipt_is_operational_only_and_keeps_exact_scientific_contract(self):
        s, fc = self.b.reconcile(T0)
        context = s['operational_fault_assessment']['desktop_acceptance_receipt']
        self.assertEqual(context['status'], 'PASS')
        self.assertEqual(context['historical_acceptance']['local_objects_verified'], 27)
        self.assertEqual(context['historical_acceptance']['r2_objects_verified'], 30)
        self.assertEqual(s['operational_fault_assessment']['all_six_desktop_archive_acceptance'], 'PASS')
        for k in ('outlook', 'alert_gates', 'known_unknowns', 'rejected_or_unknown_inputs'):
            self.assertEqual(s[k], self.baseline[k])
        cams = next(x for x in s['input_rows'] if x['source'] == builder.CAMERA)['camera_health']['private_cameras']
        before = next(x for x in self.baseline['input_rows'] if x['source'] == builder.CAMERA)['camera_health']['private_cameras']
        for a, b in zip(cams, before):
            self.assertEqual(a['raw_archive_verification'], 'PASS')
            self.assertFalse(a['negative_event_label_allowed'])
            self.assertEqual({k:v for k,v in a.items() if k!='raw_archive_verification'},
                             {k:v for k,v in b.items() if k!='raw_archive_verification'})
        provenance = s['reconciliation']['source_provenance']
        for path in (receipt.RECEIPT, self.r['provenance']['issue_comment']['path'], self.r['provenance']['verifier_report']['path'], receipt.SOURCE):
            self.assertEqual(provenance[path]['sha256'], builder.guard.digest((self.root/path).read_bytes()))
        self.assertIsNone(builder.build(self.root, T0+timedelta(seconds=1)))

    def test_stale_receipt_preserves_historical_pass_without_certifying_current_archive(self):
        s, _ = self.b.reconcile(T0+timedelta(minutes=54))
        # The latest shots are still within 60 minutes. Receipt expiry alone
        # must change consumption identity, even without any new source bytes.
        s2, _ = self.b.reconcile(T0+timedelta(minutes=55, microseconds=1))
        result = s2['operational_fault_assessment']['desktop_acceptance_receipt']
        self.assert_ignored(result, 'STALE_RECEIPT')
        self.assertEqual(result['historical_acceptance']['status'], 'PASS')
        self.assertNotEqual(s['reconciliation']['consumption_identity'], s2['reconciliation']['consumption_identity'])
        cams = next(x for x in s2['input_rows'] if x['source'] == builder.CAMERA)['camera_health']['private_cameras']
        self.assertTrue(all(c['raw_archive_verification']=='NOT_VERIFIED' for c in cams))
        self.assertIsNone(builder.build(self.root, T0+timedelta(minutes=55, microseconds=2)))

    def test_expiry_boundary_and_availability_do_not_extend_capture_freshness(self):
        self.assertEqual(self.consume(T0+timedelta(minutes=55))['status'], 'PASS')
        self.assert_ignored(self.consume(T0+timedelta(minutes=55, microseconds=1)), 'STALE_RECEIPT')
        self.assert_ignored(self.consume(T0-timedelta(microseconds=1)), 'RECEIPT_NOT_YET_AVAILABLE')

    def test_missing_receipt_does_not_fall_back_to_september_six(self):
        (self.root/receipt.RECEIPT).unlink()
        self.f.write('model_data/desktop_acceptance_20260906.json', {'status':'PASS'})
        self.b.commit('no selected receipt')
        self.assert_ignored(self.consume(), 'MISSING_RECEIPT')
        s, _ = self.b.reconcile(T0)
        self.assertEqual(s['operational_fault_assessment']['all_six_desktop_archive_acceptance'], 'NOT_VERIFIED')

    def test_uncommitted_receipt_and_evidence_are_never_consumed(self):
        expected = self.consume()
        self.f.write(receipt.RECEIPT, b'broken dirty receipt')
        self.f.write(self.r['provenance']['verifier_report']['path'], b'broken dirty evidence')
        self.assertEqual(self.consume(), expected)

    def test_new_capture_or_same_timestamp_byte_change_does_not_inherit_acceptance(self):
        self.f.write(receipt.CAMERAS[0]+'.jpg', b'\xff\xd8x\xff\xd9')
        self.b.commit('same-size changed camera bytes')
        result = self.consume()
        self.assert_ignored(result, 'CURRENT_CAPTURE_BINDING_MISMATCH')
        self.assertEqual(result['historical_acceptance']['status'], 'PASS')
        s, _ = self.b.reconcile(T0)
        self.assertEqual(s['operational_fault_assessment']['all_six_desktop_archive_acceptance'], 'NOT_VERIFIED')

    def test_runtime_source_change_retains_history_but_revokes_current_binding(self):
        self.f.write(receipt.SOURCE, b'# newer reviewed source\n')
        self.b.commit('new source')
        result = self.consume()
        self.assert_ignored(result, 'CURRENT_SOURCE_HASH_MISMATCH')
        self.assertEqual(result['historical_acceptance']['status'], 'PASS')

    def test_later_capture_does_not_inherit_earlier_archive_verification(self):
        for path in receipt.METADATA:
            d = self.f.read(path)
            d['capture_time_ct'] = (T0-timedelta(minutes=4)).isoformat()
            self.f.write(path, d)
        self.b.commit('later capture metadata')
        self.assert_ignored(self.consume(), 'CURRENT_CAPTURE_BINDING_MISMATCH')

    def test_receipt_never_bypasses_event_review_gate(self):
        d = self.f.read('vision.json')
        d['cameras'][receipt.CAMERAS[0]]['overall_jubilee_visual_signal'] = 'possible'
        self.f.write('vision.json', d)
        self.b.commit('event assessment requires review')
        with self.assertRaisesRegex(ValueError, 'REVIEW_REQUIRED'):
            builder.build(self.root, T0)

    def test_registry_change_cannot_reuse_six_camera_receipt(self):
        registry = self.f.read('model_data/camera_sources.json')
        registry['cameras'][0]['camera_id'] = 'replacement_camera'
        self.f.write('model_data/camera_sources.json', registry)
        self.b.commit('new registry')
        self.assert_ignored(self.consume(), 'CURRENT_CAMERA_SET_MISMATCH')

    def test_corrupt_or_missing_companion_evidence_fails_closed(self):
        path = self.root/self.r['provenance']['verifier_report']['path']
        for raw in (b'{}', None):
            if raw is None:
                path.unlink()
            else:
                path.write_bytes(raw)
            self.b.commit('corrupt or absent report')
            result = self.consume()
            self.assert_ignored(result, 'INVALID_OR_UNVERIFIABLE_RECEIPT')
            self.assertIsNone(result['historical_acceptance'])

    def test_malformed_schema_hash_source_parent_and_paths_are_rejected(self):
        original = copy.deepcopy(self.r)
        mutations = (
            lambda r: r.update(schema_version=0),
            lambda r: r.update(production_weight=1),
            lambda r: r.update(negative_event_label_allowed=True),
            lambda r: r['deployment'].update(deployed_sha256='0'*64),
            lambda r: r['deployment'].update(source_sha256='0'*64, deployed_sha256='0'*64),
            lambda r: r['published_files']['status.json'].update(sha256='0'*64),
            lambda r: r['published_files']['status.json'].update(git_blob='0'*40),
            lambda r: r['publication_changed_paths'].append('model_data/event_history.json'),
            lambda r: r['deployment']['required_ancestors'].update(cadence='0'*40),
            lambda r: r['provenance']['issue_comment'].update(path='../../outside'),
            lambda r: r['provenance']['issue_comment'].update(sha256='0'*64),
            lambda r: r['execution_window'].update(started_at='2026-09-28T10:55:00'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.r = copy.deepcopy(original)
                mutate(self.r)
                self.save()
                result = self.consume()
                self.assert_ignored(result, 'INVALID_OR_UNVERIFIABLE_RECEIPT')
                self.assertIsNone(result['historical_acceptance'])

    def test_nonpass_counts_camera_set_capture_and_ancestry_report_cannot_be_promoted(self):
        original = copy.deepcopy(self.report)
        mutations = (
            lambda r: r.update(status='NOT_VERIFIED'),
            lambda r: r['cameras'].pop(receipt.CAMERAS[0]),
            lambda r: r['checks']['local_archive'].update(objects_verified=26),
            lambda r: r['checks']['r2_archive'].update(objects_verified=29),
            lambda r: r['checks']['r2_archive'].update(immutable_burst_frames=17),
            lambda r: r['checks']['git_publication'].update(previous_main=r['checks']['git_publication']['current_main']),
            lambda r: r['checks']['capture'].update(capture_time_utc=(T0-timedelta(hours=2)).isoformat()),
            lambda r: r['checks']['local_archive'].update(capture_id='20260928T000000000000-0123456789ab'),
            lambda r: r['limits_minutes'].update(canonical=120),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.report = copy.deepcopy(original)
                mutate(self.report)
                self.save_report()
                self.save()
                self.assert_ignored(self.consume(), 'INVALID_OR_UNVERIFIABLE_RECEIPT')

    def test_missing_git_objects_never_fetch_or_claim_pass(self):
        reader = builder.CommittedReader(self.root)
        with patch.object(receipt.subprocess, 'run', return_value=type('Result', (), {'returncode':1})()) as run:
            self.assert_ignored(receipt.consume(reader, T0, 60), 'INVALID_OR_UNVERIFIABLE_RECEIPT')
        env = run.call_args.kwargs['env']
        self.assertEqual(env['GIT_NO_LAZY_FETCH'], '1')
        self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'], '1')

    def test_ambiguous_or_malformed_json_never_certifies_acceptance(self):
        for raw in (b'{"status":"FAIL","status":"PASS"}', b'{"production_weight":NaN}', b'null', b'[]', b'broken'):
            self.f.write(receipt.RECEIPT, raw)
            self.b.commit('malformed receipt')
            self.assert_ignored(self.consume(), 'INVALID_OR_UNVERIFIABLE_RECEIPT')


if __name__ == '__main__':
    unittest.main()

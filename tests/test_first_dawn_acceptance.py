"""Production-shaped metadata, actual JPEGs/Git ancestry, mocked GitHub receipts."""
import copy
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'model_data'))
import first_dawn_acceptance as a
import bind_current_forecast as binding
import test_current_state_freshness as environmental_fixture


def row(t, index=1):
    return dict(sha=f'{index:040x}', capture_time_ct=t.isoformat(),
                published=(t+timedelta(minutes=4)).isoformat(),
                vision={'capture_time_ct': t.isoformat(), 'cameras': {}})


class CadenceTests(unittest.TestCase):
    def rows(self):
        return [row(a.START + timedelta(minutes=5+20*i), i+2) for i in range(-1, 13)]

    def test_independent_solar_window_and_complete_regular_slots(self):
        from astral import Observer
        from astral.sun import sun
        from zoneinfo import ZoneInfo
        computed = sun(Observer(30.6035, -87.9036, 0), date=a.DAWN.date(), tzinfo=ZoneInfo('America/Chicago'))['dawn']
        self.assertEqual(computed, a.DAWN)
        errors, intervals = a.cadence(self.rows())
        self.assertEqual(errors, [])
        self.assertEqual(len(intervals), 13)
        self.assertTrue(all(i['seconds'] == 1200 for i in intervals))

    def test_baseline_dawn_handoff_under_floor_fails_with_exact_times(self):
        rows = self.rows()
        rows[0] = row(a.START-timedelta(minutes=8))
        errors, _ = a.cadence(rows)
        self.assertTrue(any('GLOBAL_SPACING' in x and '780.000000s' in x for x in errors))

    def test_publication_to_next_start_is_a_separate_floor(self):
        rows = self.rows()
        rows[0]['published'] = (a.START-timedelta(minutes=5)).isoformat()
        errors, _ = a.cadence(rows)
        self.assertTrue(any('COMPLETION_FLOOR' in x for x in errors))

    def test_missing_slot_and_duplicate_without_activity_fail(self):
        rows = self.rows()
        del rows[3]
        rows.insert(2, row(a.START+timedelta(minutes=19), 99))
        errors, _ = a.cadence(rows)
        self.assertTrue(any('MISSING_REGULAR_SLOTS' in x for x in errors))
        self.assertTrue(any('UNJUSTIFIED_ADAPTIVE' in x for x in errors))

    def test_adaptive_requires_fresh_strong_predawn_evidence(self):
        rows = self.rows()
        # A short production-shaped cycle permits a second capture in slot 0.
        rows[1] = row(a.START+timedelta(seconds=1), 2)
        rows[1]['published'] = (a.START+timedelta(seconds=31)).isoformat()
        rows[1]['vision']['cameras'] = {'montrose_shoreline': {'status': 'ok', 'flashlight_activity': 'clear'}}
        adaptive = row(a.START+timedelta(minutes=16), 99)
        adaptive['published'] = (a.START+timedelta(minutes=16, seconds=30)).isoformat()
        # Shift next regular capture within its existing nominal slot to retain
        # the global completion floor after the explicitly justified extra.
        rows[2] = row(a.START+timedelta(minutes=32), 3)
        rows[3] = row(a.START+timedelta(minutes=51), 4)
        rows[4] = row(a.START+timedelta(minutes=70), 5)
        rows[5] = row(a.START+timedelta(minutes=89), 6)
        rows[6] = row(a.START+timedelta(minutes=108), 7)
        rows[7] = row(a.START+timedelta(minutes=127), 8)
        rows.insert(2, adaptive)
        errors, _ = a.cadence(rows)
        self.assertFalse(any('UNJUSTIFIED_ADAPTIVE' in x for x in errors))
        self.assertEqual(adaptive['activity_evidence'], ['montrose_shoreline.flashlight_activity=clear'])
        weak = copy.deepcopy(rows[1]['vision'])
        weak['cameras']['montrose_shoreline']['flashlight_activity'] = 'possible'
        self.assertEqual(a.activity_reasons(weak, a.START+timedelta(minutes=16)), [])
        self.assertEqual(a.activity_reasons(rows[1]['vision'], a.START+timedelta(minutes=61)), [])
        after = self.rows()
        after.insert(9, row(a.START+timedelta(minutes=159), 99))
        after[8]['vision']['cross_camera'] = {'overall_visual_jubilee_signal': 'strong'}
        self.assertTrue(any('UNJUSTIFIED_ADAPTIVE' in x for x in a.cadence(after)[0]))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f = environmental_fixture.FreshnessTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.f.write('model_data/camera_sources.json', {'cameras': [{'camera_id': c, 'access': 'owner_google'} for c in a.CAMERAS]})
        t = a.START-timedelta(hours=1)
        self.f.asos(t, t)
        self.f.river(t, t)
        self.f.weeks(t, t)
        for name in environmental_fixture.guard.MODEL_PRODUCTS:
            self.f.write('model_data/'+name+'_manifest.json', {'retrieved_at': t.isoformat(), 'status': 'unavailable'})
        self.base = self.commit('reviewed deployment', t)
        self.addCleanup(patch.stopall)
        patch.object(a, 'DEPLOYED', self.base).start()
        patch.object(a, 'RECONCILER', self.base).start()
        self.runs = []
        self.real_schema = json.loads((ROOT/'tests/fixtures/desktop_shot_metadata.json').read_text())
        self.state = json.loads((ROOT/'tests/fixtures/state_reconciliation/snapshot_20260928T1023.json').read_text())
        self.first = self.make_cycle(a.START+timedelta(minutes=5))

    def commit(self, message, t):
        self.f.git('add', '.')
        env = dict(os.environ, GIT_AUTHOR_DATE=t.isoformat(), GIT_COMMITTER_DATE=t.isoformat())
        subprocess.run(['git', '-C', str(self.root), 'commit', '--allow-empty', '-qm', message], env=env, check=True)
        return self.f.git('rev-parse', 'HEAD')

    def make_cycle(self, t):
        from PIL import Image
        output = io.BytesIO()
        Image.new('RGB', (12, 12), 'blue').save(output, format='JPEG')
        pixels = output.getvalue()
        docs = {n: dict(capture_time_ct=t.isoformat(), dawn_ct=a.DAWN.isoformat(),
                        window_start_ct=a.START.isoformat(), window_end_ct=a.END.isoformat(),
                        burst_count=3, cameras={}) for n in a.METADATA}
        docs['vision.json']['analysis_type'] = 'three_frame_temporal_burst'
        for i, c in enumerate(a.CAMERAS):
            shots, vision_shots = copy.deepcopy(self.real_schema['shots']), copy.deepcopy(self.real_schema['burst_shots'])
            for records in (shots, vision_shots):
                for j, item in enumerate(records):
                    item.update(file=f'{c}_{j+1}.jpg', bytes=len(pixels),
                                timestamp_ct=(t+timedelta(seconds=i*30+(j+1)*10)).isoformat())
            docs['status.json']['cameras'][c] = dict(ok=True, burst_count=3, bytes=len(pixels), timestamp_ct=shots[-1]['timestamp_ct'])
            docs['burst_status.json']['cameras'][c] = dict(ok=True, shots=shots)
            docs['vision.json']['cameras'][c] = dict(camera_id=c, status='ok', burst_frame_count=3, burst_shots=vision_shots,
                                                    visibility='poor', detectability='unknown', overall_jubilee_visual_signal='none')
            self.f.write(c+'.jpg', pixels)
        for name, value in docs.items():
            self.f.write(name, value)
        r = row(t, 1)
        r['sha'] = self.commit(a.PREFIX+t.isoformat(), t+timedelta(minutes=4))
        return a.validate_camera(self.root, r)

    def downstream(self, r):
        t = a.stamp(r['capture_time_ct'])
        name = 'model_data/observation_records/'+a.digest(r['capture_time_ct'].encode())[:24]+'.json'
        obs = dict(generated_from_capture_time_ct=r['capture_time_ct'], input_hashes=r['input_hashes'],
                   clean_training_negative_count=0, production_action='NO_CHANGE', cells=[{'camera_rows': [
                       dict(camera_id=c, capture_ok=True, integrity_issues=[]) for c in a.CAMERAS]}])
        self.f.write(name, obs)
        observed = self.commit('immutable observation', t+timedelta(minutes=4, seconds=10))
        state = copy.deepcopy(self.state)
        state['snapshot_time_ct'] = (t+timedelta(minutes=5)).isoformat()
        paths = [p for p in self.f.git('ls-files').splitlines() if p not in (a.SNAPSHOT, a.FORECAST) and '/observation_records/' not in p]
        state['reconciliation'].update(input_commit_sha=observed, as_of_utc=state['snapshot_time_ct'],
            source_provenance={p: {'sha256': a.digest(a.blob(self.root, observed, p))} for p in paths})
        raw = (json.dumps(state)+'\n').encode()
        self.f.write(a.SNAPSHOT, raw)
        self.f.write(a.FORECAST, binding.project(raw))
        reconciled = self.commit('reconciled pair', t+timedelta(minutes=5, seconds=10))
        number = len(self.runs)+1
        self.runs.extend([
            dict(id=number, workflow='observation_logging.yml', head_sha=r['sha'], conclusion='success', jobs=[
                dict(name='record', conclusion='success', objects=[dict(status='published', record=name, commit=observed)])]),
            dict(id=number+1, workflow='current_state_freshness.yml', head_sha=r['sha'], conclusion='success', jobs=[
                dict(name='reconcile', conclusion='success', objects=[dict(status='published', commit=reconciled, evidence_commit=observed)]),
                dict(name='current-state-status', conclusion='success', objects=[dict(status='CURRENT', snapshot_sha256=a.digest(raw), sources=[])])])])
        return reconciled

    def test_real_git_camera_metadata_passes_and_failures_are_explicit(self):
        self.assertEqual(self.first['errors'], [])
        vision = self.f.read('vision.json')
        vision['cameras'][a.CAMERAS[0]]['burst_shots'][0]['file'] = 'wrong_camera_1.jpg'
        self.f.write('vision.json', vision)
        broken = copy.deepcopy(self.first)
        broken['sha'] = self.commit('broken vision', a.START+timedelta(minutes=9))
        errors = a.validate_camera(self.root, broken)['errors']
        self.assertTrue(any('exact shots' in e for e in errors))
        self.assertTrue(any('missing metadata' in e for e in errors))

    def test_camera_failure_and_extra_identity_fail(self):
        vision = self.f.read('vision.json')
        vision['cameras'][a.CAMERAS[-1]]['status'] = 'failed'
        vision['cameras']['unexpected_camera'] = {}
        self.f.write('vision.json', vision)
        broken = copy.deepcopy(self.first)
        broken['sha'] = self.commit('failed camera', a.START+timedelta(minutes=9))
        errors = a.validate_camera(self.root, broken)['errors']
        self.assertTrue(any('six-camera' in e for e in errors))
        self.assertTrue(any('not all successful' in e for e in errors))

    def test_first_event_only_and_non_target_dates_do_not_arm(self):
        self.assertTrue(a.eligible(self.root, self.first['sha']))
        later = self.make_cycle(a.START+timedelta(minutes=25))
        self.assertFalse(a.eligible(self.root, later['sha']))
        with patch.object(a, 'START', a.START+timedelta(days=1)), patch.object(a, 'END', a.END+timedelta(days=1)):
            self.assertFalse(a.eligible(self.root, later['sha']))

    def test_matching_observation_and_bound_reconciliation_receipts(self):
        ref = self.downstream(self.first)
        self.assertEqual(a.observation_check(self.root, ref, self.first, self.runs)['run_id'], 1)
        self.assertEqual(a.reconciliation_check(self.root, ref, self.first, self.runs)['run_id'], 2)
        bad = copy.deepcopy(self.runs)
        bad[-1]['jobs'][-1]['objects'][0]['status'] = 'PENDING_RECONCILIATION'
        with self.assertRaisesRegex(ValueError, 'no successful reconciliation'):
            a.reconciliation_check(self.root, ref, self.first, bad)
        bad = copy.deepcopy(self.runs)
        bad[0]['conclusion'] = 'cancelled'
        with self.assertRaisesRegex(ValueError, 'no successful unattended'):
            a.observation_check(self.root, ref, self.first, bad)
        # The same cancelled event is acceptable only with matching replacement evidence.
        self.assertEqual(a.observation_check(self.root, ref, self.first, bad+self.runs)['run_id'], 1)

    def test_changed_observation_hash_and_unbound_forecast_fail(self):
        ref = self.downstream(self.first)
        fake = copy.deepcopy(self.first)
        fake['input_hashes']['vision.json'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'hash/guardrail'):
            a.observation_check(self.root, ref, fake, self.runs)
        forecast = self.f.read(a.FORECAST)
        forecast['input_snapshot_hash'] = 'f'*64
        self.f.write(a.FORECAST, forecast)
        bad = self.commit('bad binding', a.START+timedelta(minutes=11))
        runs = copy.deepcopy(self.runs)
        runs[-1]['jobs'][0]['objects'][0]['commit'] = bad
        with self.assertRaisesRegex(ValueError, 'Forecast/snapshot mismatch'):
            a.reconciliation_check(self.root, bad, self.first, runs)

    def test_full_window_real_git_and_guard_pass_without_writing_production(self):
        # Recreate chronology from the known reviewed base, before the first dawn capture.
        self.f.git('reset', '--hard', self.base)
        rows = []
        for i in range(-1, 13):
            r = self.make_cycle(a.START+timedelta(minutes=5+20*i))
            ref = self.downstream(r)
            rows.append(r)
        before = self.f.git('status', '--porcelain')
        report = a.audit(self.root, ref, self.runs, a.END+timedelta(minutes=11))
        self.assertEqual(report['status'], 'PASS', json.dumps(report.get('errors'))+' '+json.dumps(report.get('pending')))
        self.assertEqual(len(report['captures']), 14)
        self.assertEqual(report['freshness']['status'], 'CURRENT')
        self.assertEqual(self.f.git('status', '--porcelain'), before)
        self.assertEqual(self.f.git('rev-parse', 'HEAD'), ref)
        bad = copy.deepcopy(self.runs)
        bad[3]['conclusion'] = 'failure'
        failed = a.audit(self.root, ref, bad, a.END+timedelta(minutes=11))
        self.assertEqual(failed['status'], 'FAIL')
        self.assertTrue(any('WORKFLOW_FAILURE' in e for e in failed['errors']))


class ReportingTests(unittest.TestCase):
    def test_incomplete_downstream_at_deadline_is_fail_not_pass(self):
        class Clock:
            @classmethod
            def now(cls, tz):
                return a.DEADLINE
        pending = dict(status='PENDING', errors=[], pending=['missing observation receipt'], captures=[])
        with tempfile.TemporaryDirectory() as temp, patch.object(a, 'datetime', Clock), \
                patch.object(a, 'git') as g, patch.object(a, 'workflow_evidence', return_value=[]), \
                patch.object(a, 'audit', return_value=pending):
            g.return_value.stdout = ('a'*40).encode()
            out = Path(temp)/'result.json'
            a.observe(Path(temp), object(), out)
            result = json.loads(out.read_text())
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('INCOMPLETE_AT_DEADLINE: missing observation receipt', result['errors'])

    def test_workflow_collection_caches_completed_attempts_but_reads_new_attempt(self):
        class API:
            def __init__(self):
                self.completed_runs, self.job_reads, self.attempt = {}, 0, 1
            def pages(self, path, key):
                if '/jobs?' in path:
                    self.job_reads += 1
                    return [dict(id=1, name='record', status='completed', conclusion='success', steps=[])]
                if 'observation_logging.yml' not in path:
                    return []
                return [dict(id=1, run_attempt=self.attempt, created_at=a.START.isoformat(),
                             event='push', head_sha='a'*40, status='completed', conclusion='success')]
            def request(self, path, raw=False):
                return '{"status":"published","record":"record.json","commit":"'+'a'*40+'"}'
        api = API()
        self.assertEqual(len(a.workflow_evidence(api)), 1)
        self.assertEqual(len(a.workflow_evidence(api)), 1)
        self.assertEqual(api.job_reads, 1)
        api.attempt = 2
        a.workflow_evidence(api)
        self.assertEqual(api.job_reads, 2)

    def test_timestamped_logs_parse_receipts_and_multiline_guard(self):
        log = ('2026-09-29T11:00:00.0000000Z {"status": "published", "record": "model_data/observation_records/a.json"}\n'
               '2026-09-29T11:00:01.0000000Z {\n2026-09-29T11:00:01.0000000Z "status": "CURRENT",\n'
               '2026-09-29T11:00:01.0000000Z "snapshot_sha256": "abc", "sources": []\n2026-09-29T11:00:01.0000000Z }')
        objects = a.log_objects(log)
        self.assertEqual([o['status'] for o in objects], ['published', 'CURRENT'])

    def test_missing_report_fails_and_repeated_delivery_does_not_post_again(self):
        class API:
            def __init__(self):
                self.saved = []
            def receipts(self):
                return self.saved
            def request(self, path, body):
                self.saved.append(body)
                return dict(body=body['body'], html_url='https://github.com/example/receipt')
        with tempfile.TemporaryDirectory() as temp:
            api = API()
            out = Path(temp)/'result.json'
            a.post_report(api, out)
            a.post_report(api, out)
            self.assertEqual(len(api.saved), 1)
            self.assertEqual(json.loads(out.read_text())['status'], 'FAIL')
            self.assertIn(a.MARKER, api.saved[0]['body'])
            self.assertIn('@bentsmith4', api.saved[0]['body'])


if __name__ == '__main__':
    unittest.main()

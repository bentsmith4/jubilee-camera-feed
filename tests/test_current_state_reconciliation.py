"""Production snapshot + six-camera/raw-archive fixtures; real Git race tests."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
import bind_current_forecast as binding
import check_current_state_freshness as guard
import reconcile_current_state as builder
import publish_current_state as publisher
import test_current_state_freshness as fixture

T0 = guard.stamp('2026-09-28T15:23:27Z')


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.FreshnessTests('test_newer_camera_data_fails_without_forecast_or_snapshot_change')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        for path in (ROOT / 'model_data').glob('*.py'):
            shutil.copy2(path, self.root / 'model_data' / path.name)
        for name in ('model_policy.md', 'operations_contract.json'):
            shutil.copy2(ROOT / 'model_data' / name, self.root / 'model_data' / name)
        self.state = json.loads((ROOT / 'tests/fixtures/state_reconciliation/snapshot_20260928T1023.json').read_bytes())
        self.f.write(binding.SNAPSHOT, self.state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(self.state)))
        self.environment(T0)
        self.cameras(T0)
        self.commit('production-shaped baseline')

    def commit(self, message):
        self.f.git('add', '.')
        self.f.git('commit', '-m', message)
        return self.f.git('rev-parse', 'HEAD')

    def cameras(self, time, failures=()):
        self.f.cameras(time - timedelta(minutes=5), failures)
        v = self.f.read('vision.json')
        for camera in v['cameras'].values():
            if camera['status'] == 'ok':
                camera.update(overall_jubilee_visual_signal='none', temporal_jubilee_signal='none',
                              visibility='good', detectability='moderate', burst_frame_count=3)
        self.f.write('vision.json', v)
        for cid in v['cameras']:
            if v['cameras'][cid]['status'] == 'ok':
                self.f.write(cid + '.jpg', b'\xff\xd8i\xff\xd9')

    def environment(self, time):
        retrieved, observed = time - timedelta(minutes=1), time - timedelta(minutes=10)
        raw = [dict(icaoId='KBFM', obsTime=int(observed.timestamp()), receiptTime=(observed+timedelta(minutes=1)).isoformat(),
                    rawOb='METAR KBFM 281500Z 27003KT', metarType='METAR', lat=30.6147, lon=-88.0630, wspd=3, wdir=270)]
        rows, _ = builder.asos.normalize(raw, retrieved)
        self.f.write('model_data/asos_weather_normalized.json', rows)
        m = dict(status='complete', retrieved_at_utc=retrieved.isoformat(), normalized_rows=len(rows),
                 normalized_sha256=guard.digest((self.root/'model_data/asos_weather_normalized.json').read_bytes()),
                 raw_path='public_archive/asos/test.json.gz',
                 raw_sha256=self.f.archive('public_archive/asos/test.json.gz', raw))
        self.f.write('model_data/asos_weather_manifest.json', m)
        self.f.river(time - timedelta(minutes=1), time - timedelta(minutes=10))
        self.f.weeks(time - timedelta(minutes=1), time - timedelta(minutes=10))
        for name in guard.MODEL_PRODUCTS:
            self.f.write('model_data/'+name+'_manifest.json', {'retrieved_at': time.isoformat(), 'status': 'unavailable'})

    def reconcile(self, now):
        result = builder.build(self.root, now)
        self.assertIsNotNone(result)
        for path, raw in zip(publisher.OUTPUTS, result):
            self.f.write(path, raw)
        snapshot, forecast = map(json.loads, result)
        binding.check(result[0], forecast)
        self.assertEqual(guard.inspect(self.root, now)['status'], 'CURRENT')
        self.assertEqual(snapshot['outlook'], self.state['outlook'])
        self.assertEqual(snapshot['alert_gates'], self.state['alert_gates'])
        binding.validate_weights(snapshot)
        self.commit('reconciled pair')
        return snapshot, forecast

    def test_back_to_back_sensing_then_camera_and_duplicate_trigger(self):
        first, _ = self.reconcile(T0)
        self.environment(T0 + timedelta(minutes=37))
        sensing = self.commit('sensing publication')
        second, _ = self.reconcile(T0 + timedelta(minutes=38))
        self.assertEqual(second['reconciliation']['input_commit_sha'], sensing)
        self.cameras(T0 + timedelta(minutes=43))
        camera = self.commit('camera publication')
        third, forecast = self.reconcile(T0 + timedelta(minutes=44))
        self.assertEqual(third['reconciliation']['input_commit_sha'], camera)
        self.assertNotEqual(first['reconciliation']['consumption_identity'], third['reconciliation']['consumption_identity'])
        self.assertEqual(forecast['data_coverage']['private_camera_metadata_pass'], 6)
        self.assertIsNone(builder.build(self.root, T0 + timedelta(minutes=45)))

    def test_camera_then_sensing_and_outage_never_consumes_retained_csv(self):
        self.reconcile(T0)
        self.cameras(T0 + timedelta(minutes=35))
        self.commit('camera first')
        self.reconcile(T0 + timedelta(minutes=36))
        self.environment(T0 + timedelta(minutes=38))
        self.f.write('model_data/ngofs2_mobile_bay_named_stations_forecast_normalized.csv', b'invalid retained CSV')
        self.f.write('model_data/river_forcing_manifest.json', {'status':'unavailable', 'retrieved_at_utc':(T0+timedelta(minutes=38)).isoformat()})
        self.commit('partial sensing publication with explicit outage')
        s, fc = self.reconcile(T0 + timedelta(minutes=39))
        self.assertEqual(fc['data_coverage']['fresh_river_series'], 0)
        self.assertNotIn('model_data/ngofs2_mobile_bay_named_stations_forecast_normalized.csv', s['reconciliation']['source_provenance'])
        self.assertIn('river_forcing: SOURCE_UNAVAILABLE/UNKNOWN', s['known_unknowns'])

    def test_dirty_and_unpublished_files_cannot_enter_state(self):
        expected = builder.build(self.root, T0)
        self.f.write('model_data/asos_weather_manifest.json', {'status': 'failed'})
        self.f.write('vision.json', b'not JSON')
        self.assertEqual(builder.build(self.root, T0), expected)

    def test_failed_or_corrupt_committed_product_is_fatal_without_pair_write(self):
        before = [(self.root / p).read_bytes() for p in publisher.OUTPUTS]
        for defect in ('failed', 'hash'):
            with self.subTest(defect=defect):
                self.environment(T0)
                m = self.f.read('model_data/asos_weather_manifest.json')
                m.update({'status':'failed'} if defect == 'failed' else {'normalized_sha256':'0'*64})
                self.f.write('model_data/asos_weather_manifest.json', m)
                self.commit(defect)
                with self.assertRaises(ValueError): builder.build(self.root, T0)
                self.assertEqual([(self.root / p).read_bytes() for p in publisher.OUTPUTS], before)

    def test_issue_time_expiry_is_unknown_and_manual_context_not_refreshed(self):
        self.reconcile(T0)
        s, _ = self.reconcile(T0 + timedelta(minutes=95))
        rows = {r['source']: r for r in s['input_rows']}
        self.assertEqual(rows[builder.ASOS]['parameter_admission']['KBFM']['parameters']['wind_speed']['value_status'], 'UNKNOWN')
        self.assertEqual(rows[builder.CAMERA]['camera_health']['private_cameras'][0]['overall_visual_signal'], 'UNKNOWN')
        self.assertEqual(rows['NOAA CO-OPS Tide Predictions']['admitted_status'], 'UNKNOWN_NOT_REASSESSED')
        self.assertEqual(rows[builder.RIVER]['series'][0]['value_status'], 'KNOWN_UPSTREAM_PROXY')

    def test_uncertain_event_or_new_fault_fails_closed(self):
        for event in ('visual', 'cross_camera', 'failed_camera', 'simultaneous_loss'):
            with self.subTest(event=event):
                self.cameras(T0)
                self.environment(T0)
                if event in ('visual', 'cross_camera'):
                    v=self.f.read('vision.json')
                    if event=='visual': v['cameras']['camera_0']['overall_jubilee_visual_signal']='possible'
                    else: v['cross_camera']={'overall_visual_jubilee_signal':'strong'}
                    self.f.write('vision.json',v)
                elif event=='failed_camera': self.cameras(T0, ('camera_0',))
                else:
                    for name in ('asos_weather','river_forcing'):
                        self.f.write('model_data/'+name+'_manifest.json', {'status':'unavailable','retrieved_at_utc':T0.isoformat()})
                self.commit(event)
                with self.assertRaisesRegex(ValueError, 'REVIEW_REQUIRED'): builder.build(self.root,T0)

    def test_low_visibility_cross_camera_unclear_remains_uncertain_context(self):
        """Production-shaped 2026-09-28 19:06 CT ambiguity must not fail closed."""
        v = self.f.read('vision.json')
        point_clear = v['cameras']['camera_3']
        point_clear.update(
            visibility='poor', detectability='low',
            overall_jubilee_visual_signal='unclear',
            temporal_jubilee_signal='unclear',
            water_surface='unclear',
            artificial_light_confounding='strong',
            rain_surface_interference='possible',
        )
        v['cross_camera'] = {
            'overall_visual_jubilee_signal': 'unclear',
            'montrose_visual_signal': 'none',
            'point_clear_visual_signal': 'unclear',
            'temporal_confirmation': 'none',
            'important_confounders': [
                'Poor Point Clear visibility',
                'Strong artificial-light reflections',
                'Possible rain or camera interference',
            ],
        }
        self.f.write('vision.json', v)
        self.commit('low-detectability cross-camera ambiguity')

        snapshot, forecast = self.reconcile(T0)
        cameras = next(row for row in snapshot['input_rows'] if row['source'] == builder.CAMERA)
        reconciled = {row['camera_id']: row for row in cameras['camera_health']['private_cameras']}
        self.assertEqual(reconciled['camera_3']['overall_visual_signal'], 'unclear')
        self.assertEqual(reconciled['camera_3']['temporal_visual_signal'], 'unclear')
        self.assertFalse(snapshot['alert_gates']['direct_event_evidence_present'])
        self.assertFalse(snapshot['reconciliation']['forecast_weights_changed'])
        self.assertEqual(forecast['outlooks'], binding.project(builder.encode(self.state))['outlooks'])

    def remote(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        remote = Path(tmp.name) / 'remote.git'
        subprocess.run(['git','init','--bare',str(remote)], check=True, capture_output=True)
        self.f.git('remote','add','origin',str(remote))
        self.f.git('push','origin','HEAD:main')
        return remote

    def remote_json(self,path):
        self.f.git('fetch','origin','main')
        return json.loads(self.f.git('show','FETCH_HEAD:'+path))

    def test_real_push_race_rebuilds_both_files_on_winning_camera_and_sensing(self):
        self.remote()
        def concurrent(attempt):
            if attempt==0:
                self.environment(T0 + timedelta(minutes=37))
                self.commit('concurrent sensing')
                self.cameras(T0 + timedelta(minutes=42))
                self.commit('concurrent camera')
                self.f.write('research-note.txt',b'preserve unrelated research')
                self.commit('concurrent unrelated metadata')
                self.winner=self.f.git('rev-parse','HEAD')
                self.f.git('push','origin','HEAD:main')
        result=publisher.publish(self.root, before_push=concurrent, as_of=(T0+timedelta(minutes=44)).isoformat())
        self.assertEqual(result['attempts'],2)
        s=self.remote_json(binding.SNAPSHOT)
        fc=self.remote_json(binding.FORECAST)
        self.assertEqual(s['reconciliation']['input_commit_sha'],self.winner)
        binding.check(builder.encode(s),fc)
        self.assertEqual(self.f.git('diff-tree','--no-commit-id','--name-only','-r',result['commit']).splitlines(), sorted(publisher.OUTPUTS))
        self.assertEqual(self.f.git('show','FETCH_HEAD:research-note.txt'),'preserve unrelated research')
        self.assertEqual(publisher.publish(self.root,as_of=(T0+timedelta(minutes=45)).isoformat())['status'],'already_current')

    def test_exhausted_races_never_publish_stale_candidate(self):
        self.remote()
        def concurrent(attempt):
            self.f.write('research-note.txt', str(attempt).encode())
            self.commit('race '+str(attempt))
            self.f.git('push','origin','HEAD:main')
        with self.assertRaisesRegex(RuntimeError,'bounded reconciliation retries exhausted'):
            publisher.publish(self.root, attempts=2,before_push=concurrent,as_of=T0.isoformat())
        self.assertEqual(self.remote_json(binding.SNAPSHOT), self.state)

    def test_noop_race_rechecks_remote_before_claiming_current(self):
        self.reconcile(T0)
        self.remote()
        def concurrent(attempt):
            if attempt==0:
                self.environment(T0+timedelta(minutes=2))
                self.commit('source advances after no-op')
                self.f.git('push','origin','HEAD:main')
        result=publisher.publish(self.root,before_push=concurrent,as_of=(T0+timedelta(minutes=3)).isoformat())
        self.assertEqual(result['status'],'published')
        self.assertEqual(result['attempts'],2)

    def test_concurrent_reviewed_state_is_preserved_on_retry(self):
        self.remote()
        def concurrent(attempt):
            if attempt == 0:
                state = copy.deepcopy(self.state)
                state['outlook'][0]['point_clear_central_percent'] = 4
                self.f.write(binding.SNAPSHOT, state)
                self.f.write(binding.FORECAST, binding.project(builder.encode(state)))
                self.commit('concurrent explicitly reviewed heuristic state')
                self.f.git('push','origin','HEAD:main')
        result = publisher.publish(self.root, before_push=concurrent, as_of=T0.isoformat())
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(self.remote_json(binding.SNAPSHOT)['outlook'][0]['point_clear_central_percent'], 4)
        self.assertEqual(self.remote_json(binding.FORECAST)['outlooks'][0]['central_percent'], 4)

    def test_asos_matching_normalized_hash_cannot_hide_raw_semantic_corruption(self):
        rows = self.f.read('model_data/asos_weather_normalized.json')
        rows[0]['value'] = 199
        self.f.write('model_data/asos_weather_normalized.json', rows)
        m = self.f.read('model_data/asos_weather_manifest.json')
        m['normalized_sha256'] = guard.digest((self.root/'model_data/asos_weather_normalized.json').read_bytes())
        self.f.write('model_data/asos_weather_manifest.json', m)
        self.commit('incorrect normalization with updated manifest hash')
        with self.assertRaisesRegex(ValueError,'ASOS archive/data mismatch'): builder.build(self.root,T0)

    def test_same_size_corrupt_jpeg_is_rejected(self):
        self.f.write('camera_0.jpg', b'wrong')
        self.commit('corrupt image with matching size')
        with self.assertRaisesRegex(ValueError,'invalid camera JPEG'): builder.build(self.root,T0)

    def test_model_recovery_and_expired_forecast_keep_model_unknown_semantics(self):
        name = 'ngofs2_mobile_bay_named_stations_forecast'
        with patch.object(fixture, 'T0', T0): self.f.model(name, 0.01)
        self.commit('model recovery')
        _, fc = self.reconcile(T0)
        self.assertEqual(fc['data_coverage']['ngofs2_products'][name], 'ADMITTED_FORWARD_MODEL_GUIDANCE')
        future = T0 + timedelta(hours=4)
        self.environment(future)
        self.cameras(future)
        with patch.object(fixture, 'T0', T0): self.f.model(name, 0.01)
        self.commit('other sources advance beyond model forecast horizon')
        s, fc = self.reconcile(future)
        self.assertEqual(fc['data_coverage']['ngofs2_products'][name], 'UNKNOWN_NO_CURRENT_GUIDANCE')
        product = next(r for r in s['input_rows'] if r['source'] == builder.MODEL)['products'][name]
        self.assertEqual(product['current_observed_transport_status'], 'UNKNOWN_NOT_AN_OBSERVATION')
        self.assertEqual(product['production_weight'], 0)

    def test_workflow_trust_and_token_push_trigger_contract(self):
        workflow=(ROOT/'.github/workflows/current_state_freshness.yml').read_text()
        for name in ('Jubilee sensing quality and environmental forcing','Jubilee official ASOS observed weather','Jubilee unattended observation logging'):
            self.assertIn(name,workflow)
        self.assertIn('needs: reconcile',workflow)
        self.assertIn("if: always() && github.event_name != 'pull_request'",workflow)
        self.assertIn('ref: main',workflow)
        self.assertNotIn('download-artifact',workflow)
        self.assertNotIn('head_sha',workflow)
        self.assertIn('cancel-in-progress: false',workflow)

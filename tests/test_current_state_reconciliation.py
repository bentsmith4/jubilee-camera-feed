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

    def test_station_expansion_replays_prior_two_airport_manifest(self):
        old_url = 'https://aviationweather.gov/api/data/metar?ids=KBFM%2CKMOB&format=json&hours=6'
        path = 'model_data/asos_weather_normalized.json'
        rows = self.f.read(path)
        for row in rows:
            row['source_url'] = old_url
        self.f.write(path, rows)
        manifest = self.f.read('model_data/asos_weather_manifest.json')
        manifest['source_url'] = old_url
        manifest['normalized_sha256'] = guard.digest((self.root/path).read_bytes())
        self.f.write('model_data/asos_weather_manifest.json', manifest)
        self.commit('preserve pre-expansion weather provenance')
        snapshot, _ = self.reconcile(T0)
        weather = next(row for row in snapshot['input_rows'] if row['source'] == builder.ASOS)
        self.assertEqual(weather['parameter_admission']['KCQF']['status'], 'UNKNOWN')
        self.assertEqual(weather['parameter_admission']['KBFM']['parameters']['wind_speed']['source_url'], old_url)
        self.assertIn('KCQF', weather['station_location'])

    def fish_river(self, observed, defect=None, include_upstream=True):
        import gzip
        raw = json.loads(gzip.decompress((self.root / 'model_data/public_archive/usgs/test.json.gz').read_bytes()))
        if not include_upstream:
            raw['value']['timeSeries'] = []
        fish = json.loads((ROOT / 'tests/fixtures/fish_river/usgs_02378500_20261018.json').read_bytes())
        for ts in fish['value']['timeSeries']:
            group = ts['values'][0]
            group['value'] = [group['value'][-1]]
            group['value'][0]['dateTime'] = observed.isoformat()
            if defect == 'units': ts['variable']['unit']['unitCode'] = 'WRONG'
            if defect == 'qc': group['value'][0]['qualifiers'] = ['P', 'UNKNOWN']
            if defect == 'conflict':
                conflict = copy.deepcopy(group['value'][0])
                conflict['value'] = str(float(conflict['value']) + 1)
                group['value'].append(conflict)
        raw['value']['timeSeries'].extend(fish['value']['timeSeries'])
        m = self.f.read('model_data/river_forcing_manifest.json')
        m.update(status='partial', requested_sites=list(builder.river.SITES),
                 missing_sites=['02469761', '02469762'] if include_upstream else list(builder.river.UPSTREAM_SITES),
                 raw_sha256=self.f.archive('public_archive/usgs/test.json.gz', raw),
                 normalized_rows=len(builder.river.normalize(raw, guard.stamp(m['retrieved_at_utc']), m['source_url'])))
        self.f.write('model_data/river_forcing_manifest.json', m)
        self.commit('add separate synthetic Fish River evidence')

    def test_fish_river_is_separate_from_upstream_and_forecast_count(self):
        self.fish_river(T0 - timedelta(minutes=10))
        snapshot, forecast = self.reconcile(T0)
        rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
        self.assertEqual({r['station_id'] for r in rv['series']}, {'02428400'})
        local = rv['local_watershed_context']
        self.assertEqual(local['value_status'], 'KNOWN_LOCAL_WATERSHED_PROXY')
        self.assertEqual(local['missing_parameter_codes'], [])
        self.assertEqual(len(local['series']), 2)
        self.assertEqual(forecast['data_coverage']['fresh_river_series'], 1)
        self.assertEqual({r['station_id'] for r in local['series']}, {'02378500'})
        self.assertTrue(all(r['production_weight'] == 0 and 'antecedent_windows' not in r for r in local['series']))
        self.assertIn('native-gage', local['observation'])

    def test_fish_river_stale_future_qc_units_and_conflicts_remain_unknown(self):
        for defect in ('stale', 'future', 'qc', 'units', 'conflict'):
            with self.subTest(defect=defect):
                self.environment(T0)
                observed = T0 + timedelta(minutes=1) if defect == 'future' else T0 - timedelta(minutes=181 if defect == 'stale' else 10)
                self.fish_river(observed, defect)
                snapshot, forecast = self.reconcile(T0)
                rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
                self.assertEqual(rv['local_watershed_context']['value_status'], 'UNKNOWN')
                self.assertTrue(all(r['latest_value'] is None for r in rv['local_watershed_context']['series']))
                self.assertEqual(forecast['data_coverage']['fresh_river_series'], 1)

    def test_fish_river_expiry_reconciles_without_new_raw_observation(self):
        self.fish_river(T0 - timedelta(minutes=179))
        snapshot, _ = self.reconcile(T0)
        rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
        self.assertEqual(rv['local_watershed_context']['value_status'], 'KNOWN_LOCAL_WATERSHED_PROXY')
        snapshot, forecast = self.reconcile(T0 + timedelta(minutes=2))
        rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
        self.assertEqual(rv['local_watershed_context']['value_status'], 'UNKNOWN')
        self.assertEqual(forecast['data_coverage']['fresh_river_series'], 1)

    def test_missing_fish_river_and_legacy_three_station_replay(self):
        import gzip
        raw = json.loads(gzip.decompress((self.root / 'model_data/public_archive/usgs/test.json.gz').read_bytes()))
        for station in ('02469761', '02469762'):
            ts = copy.deepcopy(raw['value']['timeSeries'][0])
            ts['sourceInfo']['siteCode'][0]['value'] = station
            ts['name'] = 'USGS:' + station + ':00060'
            raw['value']['timeSeries'].append(ts)
        m = self.f.read('model_data/river_forcing_manifest.json')
        m.update(source_url='https://waterservices.usgs.gov/nwis/iv/?sites=02428400,02469761,02469762',
                 normalized_rows=3, raw_sha256=self.f.archive('public_archive/usgs/test.json.gz', raw))
        # Historical complete response remains valid; expanded partial response
        # cannot admit a missing new station or reject the three existing ones.
        for status in ('complete', 'partial'):
            m['status'] = status
            if status == 'partial': m.update(requested_sites=list(builder.river.SITES), missing_sites=['02378500'])
            self.f.write('model_data/river_forcing_manifest.json', m)
            self.commit('legacy or expanded three-station response ' + status)
            snapshot, forecast = self.reconcile(T0)
            rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
            self.assertEqual(forecast['data_coverage']['fresh_river_series'], 3)
            self.assertEqual(rv['local_watershed_context']['value_status'], 'UNKNOWN')
            self.assertEqual(rv['local_watershed_context']['series'], [])
            self.assertEqual(rv['local_watershed_context']['missing_parameter_codes'], ['00060', '00065'])

    def test_fish_river_alone_cannot_replace_missing_upstream(self):
        self.fish_river(T0 - timedelta(minutes=10), include_upstream=False)
        snapshot, forecast = self.reconcile(T0)
        rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
        self.assertEqual(rv['series'], [])
        self.assertEqual(rv['admitted_status'], 'UNKNOWN')
        self.assertEqual(rv['local_watershed_context']['value_status'], 'KNOWN_LOCAL_WATERSHED_PROXY')
        self.assertEqual(forecast['data_coverage']['fresh_river_series'], 0)

    def test_fish_river_outage_does_not_reuse_retained_raw(self):
        self.fish_river(T0 - timedelta(minutes=10))
        self.reconcile(T0)
        self.f.write('model_data/river_forcing_manifest.json', {'status': 'unavailable', 'retrieved_at_utc': T0.isoformat()})
        self.commit('explicit outage with retained old raw')
        snapshot, forecast = self.reconcile(T0 + timedelta(minutes=1))
        rv = next(r for r in snapshot['input_rows'] if r['source'] == builder.RIVER)
        self.assertEqual(rv['local_watershed_context']['value_status'], 'UNKNOWN')
        self.assertEqual(rv['local_watershed_context']['series'], [])
        self.assertEqual(forecast['data_coverage']['fresh_river_series'], 0)

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

    def test_active_material_input_fault_does_not_freeze_source_reconciliation(self):
        state = copy.deepcopy(self.state)
        state["alert_gates"]["material_critical_input_fault"] = True
        state["alert_gates"]["notification_suppressed"] = False
        state["notification_condition_met"] = True
        state.setdefault("operational_fault_assessment", {})
        state["operational_fault_assessment"].update(active_fault_present=True, failed_camera_ids=[])
        self.f.write(binding.SNAPSHOT, state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(state)))
        self.commit("assessed material input-quality fault")

        later = T0 + timedelta(minutes=10)
        self.environment(later)
        self.cameras(later, ('camera_0',))
        self.commit("fresh sources and changed camera health while assessed fault remains active")

        result = builder.build(self.root, later + timedelta(minutes=1))
        self.assertIsNotNone(result)
        snapshot, forecast = map(json.loads, result)
        self.assertTrue(snapshot["alert_gates"]["material_critical_input_fault"])
        self.assertTrue(snapshot["notification_condition_met"])
        self.assertTrue(snapshot["operational_fault_assessment"]["assessed_material_critical_input_fault_preserved"])
        self.assertTrue(snapshot["operational_fault_assessment"]["camera_failure_set_changed_under_preserved_material_fault"])
        self.assertEqual(snapshot["operational_fault_assessment"]["failed_camera_ids"], ["camera_0"])
        rows = {r["source"]: r for r in snapshot["input_rows"]}
        self.assertEqual(rows[builder.ASOS]["parameter_admission"]["KBFM"]["parameters"]["wind_speed"]["value_status"], "KNOWN")
        self.assertTrue(any(x["value_status"] == "KNOWN_UPSTREAM_PROXY" for x in rows[builder.RIVER]["series"]))
        binding.check(result[0], forecast)

    def test_active_material_fault_allows_simultaneous_weather_river_loss(self):
        state = copy.deepcopy(self.state)
        state["alert_gates"]["material_critical_input_fault"] = True
        state["alert_gates"]["notification_suppressed"] = False
        state["notification_condition_met"] = True
        state.setdefault("operational_fault_assessment", {})
        state["operational_fault_assessment"].update(active_fault_present=True, failed_camera_ids=[])
        self.f.write(binding.SNAPSHOT, state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(state)))
        self.commit("assessed material input-quality fault")

        later = T0 + timedelta(minutes=10)
        self.cameras(later)
        for name in ("asos_weather", "river_forcing"):
            self.f.write("model_data/" + name + "_manifest.json",
                         {"status": "unavailable", "retrieved_at_utc": later.isoformat()})
        self.commit("weather and river unavailable while assessed fault remains active")

        result = builder.build(self.root, later + timedelta(minutes=1))
        self.assertIsNotNone(result)
        snapshot, forecast = map(json.loads, result)
        self.assertTrue(snapshot["alert_gates"]["material_critical_input_fault"])
        self.assertTrue(snapshot["notification_condition_met"])
        self.assertTrue(snapshot["operational_fault_assessment"]["assessed_material_critical_input_fault_preserved"])
        self.assertIn("asos_weather: SOURCE_UNAVAILABLE/UNKNOWN", snapshot["known_unknowns"])
        self.assertIn("river_forcing: SOURCE_UNAVAILABLE/UNKNOWN", snapshot["known_unknowns"])
        binding.check(result[0], forecast)

    def test_partial_and_total_camera_loss_require_review_without_overwriting_pair(self):
        before = [(self.root / p).read_bytes() for p in publisher.OUTPUTS]
        for failures in (('camera_0', 'camera_1', 'camera_2'),
                         tuple('camera_' + str(i) for i in range(6))):
            with self.subTest(failures=failures):
                self.cameras(T0, failures)
                self.commit('new partial or complete camera outage')
                with self.assertRaisesRegex(ValueError, 'REVIEW_REQUIRED: changed camera failures'):
                    builder.build(self.root, T0)
                self.assertEqual([(self.root / p).read_bytes() for p in publisher.OUTPUTS], before)

    def test_assessed_partial_and_total_camera_outages_keep_unknown_and_frozen_forecast(self):
        state = copy.deepcopy(self.state)
        state['alert_gates']['material_critical_input_fault'] = True
        state['alert_gates']['notification_suppressed'] = False
        state['notification_condition_met'] = True
        state.setdefault('operational_fault_assessment', {}).update(
            active_fault_present=True, failed_camera_ids=[])
        self.f.write(binding.SNAPSHOT, state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(state)))
        self.commit('existing assessed material fault for outage fixture')
        for failures in (('camera_0', 'camera_1', 'camera_2'),
                         tuple('camera_' + str(i) for i in range(6))):
            with self.subTest(failures=failures):
                self.cameras(T0, failures)
                # Old JPEGs deliberately remain in the repository fixture.
                self.commit('assessed outage with retained old images')
                result = builder.build(self.root, T0)
                snapshot, forecast = map(json.loads, result)
                binding.check(result[0], forecast)
                binding.validate_weights(snapshot)
                self.assertEqual(snapshot['alert_gates'], state['alert_gates'])
                self.assertEqual(snapshot['outlook'], state['outlook'])
                self.assertEqual(forecast['outlooks'], binding.project(builder.encode(state))['outlooks'])
                health = next(r for r in snapshot['input_rows'] if r['source'] == builder.CAMERA)['camera_health']
                self.assertEqual(health['private_metadata_pass'], 6-len(failures))
                self.assertEqual(sorted(health['unknown_upstream_camera_ids']), sorted(failures))
                for row in health['private_cameras']:
                    self.assertFalse(row['negative_event_label_allowed'])
                    if row['camera_id'] in failures:
                        self.assertEqual(row['admitted_status'], 'UNKNOWN_STALE_OR_FAILED')
                        for field in ('visibility', 'biological_detectability', 'overall_visual_signal', 'temporal_visual_signal'):
                            self.assertEqual(row[field], 'UNKNOWN')
                    else:
                        self.assertEqual(row['admitted_status'], 'ADMITTED_VISIBLE_SCOPE_CONTEXT')

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
            'temporal_confirmation': 'limited',
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

    def reviewed_camera_fixture(self, now):
        """Exact PR #111 JSON, synthetic final-image bytes and environment."""
        source = ROOT / 'tests/fixtures/state_reconciliation/reviewed_camera_20261018'
        for path in source.rglob('*'):
            if path.is_file() and path.name != 'README.md':
                self.f.write(str(path.relative_to(source)), path.read_bytes())
        original = (self.root / binding.SNAPSHOT).read_bytes()
        self.assertEqual(guard.digest(original), '62504f99b9b0e4263a79b2b8a8030b1fe0bbdad3c4803c3fc6d2ff2656a1e24e')
        binding.check(original, self.f.read(binding.FORECAST))
        self.state = json.loads(original)
        status = self.f.read('status.json')
        # Avoid storing another copy of private camera pixels. Only image bytes
        # and their provenance are synthetic; all reviewed JSON stays exact.
        for cid, camera in status['cameras'].items():
            self.f.write(cid + '.jpg', b'\xff\xd8' + b'0' * (camera['bytes'] - 4) + b'\xff\xd9')
        self.environment(now)
        self.commit('PR 111 JSON with synthetic images and environmental refresh')
        for cid in status['cameras']:
            path = cid + '.jpg'
            self.state['reconciliation']['source_provenance'][path] = dict(
                sha256=guard.digest((self.root/path).read_bytes()),
                git_blob=self.f.git('rev-parse', 'HEAD:' + path))
        self.f.write(binding.SNAPSHOT, self.state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(self.state)))
        self.commit('bind synthetic image provenance for fixture-only replay')
        return copy.deepcopy(self.state['manual_event_review'])

    def owner_expired_review_fixture(self, now):
        """Exact cab3 camera row/issue clock; image/environment fixtures synthetic.

        Owner snapshot blob a5e63985575337ddf248789c6f82a34814656fc3,
        commit cab3d08f2923d5e7675bffae071ea71de0702f2e. Its original
        manual_event_review and all eleven camera provenance entries are
        unchanged from PR #111. No new camera review is manufactured here.
        """
        review = self.reviewed_camera_fixture(now)
        owner_row = json.loads(r'''{
  "source": "bentsmith4/jubilee-camera-feed status.json, burst_status.json and vision.json",
  "station_location": "six owner cameras at Montrose and Point Clear",
  "parameter": "three-frame visual evidence and camera health",
  "observed_vs_predicted_model": "OWNER_CAMERA_OBSERVATION_PLUS_VISION_CLASSIFICATION",
  "units": "categorical visual evidence",
  "timezone_datum_depth": "explicit ISO-8601 CDT offsets; camera-visible surface/shoreline only",
  "shoreline_cell": "Montrose and Point Clear",
  "independence_group": "montrose_owner_cluster + point_clear_landing_owner_cluster",
  "valid_time_ct": "2026-10-18T22:06:04.956448-05:00",
  "evaluated_at_ct": "2026-10-18T23:47:03.143694-05:00",
  "admitted_status": "VISIBLE_SCOPE_CONTEXT_WITH_EXPLICIT_HEALTH_AND_AGE",
  "observation": "Committed vision classifications only. Unknown or absent visible signals do not establish biological absence or dawn acceptance.",
  "camera_health": {
    "expected_private_cameras": 6,
    "private_metadata_pass": 6,
    "private_cameras": [
      {
        "camera_id": "montrose_pier_boat",
        "site_group": "montrose_owner_cluster",
        "shoreline_cell": "Montrose",
        "captured_at_ct": "2026-10-18T22:06:33.827405-05:00",
        "age_minutes": 100.489,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN",
        "temporal_visual_signal": "UNKNOWN",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      },
      {
        "camera_id": "montrose_pier_bird",
        "site_group": "montrose_owner_cluster",
        "shoreline_cell": "Montrose",
        "captured_at_ct": "2026-10-18T22:09:21.781795-05:00",
        "age_minutes": 97.689,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN",
        "temporal_visual_signal": "UNKNOWN",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      },
      {
        "camera_id": "montrose_shoreline",
        "site_group": "montrose_owner_cluster",
        "shoreline_cell": "Montrose",
        "captured_at_ct": "2026-10-18T22:08:13.650556-05:00",
        "age_minutes": 98.825,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN",
        "temporal_visual_signal": "UNKNOWN",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      },
      {
        "camera_id": "pcl_e2_back_deck",
        "site_group": "point_clear_landing_owner_cluster",
        "shoreline_cell": "Point Clear",
        "captured_at_ct": "2026-10-18T22:07:16.809571-05:00",
        "age_minutes": 99.772,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN_REVIEWED_LOW_DETECTABILITY",
        "temporal_visual_signal": "UNKNOWN_REVIEWED_LOW_DETECTABILITY",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      },
      {
        "camera_id": "pcl_e2_bay_mouth",
        "site_group": "point_clear_landing_owner_cluster",
        "shoreline_cell": "Point Clear",
        "captured_at_ct": "2026-10-18T22:07:44.605948-05:00",
        "age_minutes": 99.309,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN",
        "temporal_visual_signal": "UNKNOWN",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      },
      {
        "camera_id": "pcl_e3_bay_mouth",
        "site_group": "point_clear_landing_owner_cluster",
        "shoreline_cell": "Point Clear",
        "captured_at_ct": "2026-10-18T22:08:54.626713-05:00",
        "age_minutes": 98.142,
        "upstream_metadata_pass": true,
        "admitted_status": "UNKNOWN_STALE_OR_FAILED",
        "visibility": "UNKNOWN",
        "biological_detectability": "UNKNOWN",
        "overall_visual_signal": "UNKNOWN",
        "temporal_visual_signal": "UNKNOWN",
        "negative_event_label_allowed": false,
        "raw_archive_verification": "NOT_VERIFIED"
      }
    ],
    "unknown_upstream_camera_ids": []
  }
}''')
        self.state['snapshot_time_ct'] = '2026-10-18T23:47:03.143694-05:00'
        self.state['reconciliation']['as_of_utc'] = '2026-10-19T04:47:03.143694+00:00'
        self.state['input_rows'] = [owner_row if row['source'] == builder.CAMERA else row
                                    for row in self.state['input_rows']]
        self.f.write(binding.SNAPSHOT, self.state)
        self.f.write(binding.FORECAST, binding.project(builder.encode(self.state)))
        self.commit('exact cab3 owner stale camera-row shape')
        return review

    def assert_review_failure_keeps_pair(self, now, message='REVIEW_REQUIRED'):
        before = [(self.root / p).read_bytes() for p in publisher.OUTPUTS]
        with self.assertRaisesRegex(ValueError, message):
            builder.build(self.root, now)
        self.assertEqual([(self.root / p).read_bytes() for p in publisher.OUTPUTS], before)

    def test_pr111_expiry_allows_environment_refresh_without_reviving_review(self):
        now = guard.stamp('2026-10-19T04:32:41Z')
        review = self.reviewed_camera_fixture(now)
        snapshot, forecast = self.reconcile(now)
        self.assertEqual(snapshot['manual_event_review'], review)
        camera_row = next(r for r in snapshot['input_rows'] if r['source'] == builder.CAMERA)
        target = next(r for r in camera_row['camera_health']['private_cameras'] if r['camera_id'] == review['camera_id'])
        self.assertEqual(target['admitted_status'], 'UNKNOWN_STALE')
        self.assertEqual(target['captured_at_ct'], '2026-10-18T22:07:16.809571-05:00')
        self.assertEqual(review['capture_time_ct'], '2026-10-18T22:06:04.956448-05:00')
        for field in ('visibility', 'biological_detectability', 'overall_visual_signal', 'temporal_visual_signal'):
            self.assertEqual(target[field], 'UNKNOWN')
        self.assertFalse(target['negative_event_label_allowed'])
        self.assertTrue(any('historical only' in text for text in snapshot['known_unknowns']))
        self.assertEqual(forecast['outlooks'], binding.project(builder.encode(self.state))['outlooks'])
        # Another non-camera update remains possible without refreshing the review.
        self.environment(now + timedelta(minutes=10))
        self.commit('second synthetic environmental refresh')
        second, _ = self.reconcile(now + timedelta(minutes=10))
        self.assertEqual(second['manual_event_review'], review)
        self.assertIsNone(builder.build(self.root, now + timedelta(minutes=11)))

    def test_cab3_owner_stale_review_refreshes_without_changing_assessment(self):
        now = guard.stamp('2026-10-19T04:55:12Z')
        review = self.owner_expired_review_fixture(now)
        snapshot, _ = self.reconcile(now)
        self.assertEqual(snapshot['manual_event_review'], review)
        self.assertEqual(snapshot['reconciliation']['prior_snapshot_time_ct'], '2026-10-18T23:47:03.143694-05:00')
        row = next(r for r in snapshot['input_rows'] if r['source'] == builder.CAMERA)
        target = next(r for r in row['camera_health']['private_cameras'] if r['camera_id'] == review['camera_id'])
        self.assertEqual(target['admitted_status'], 'UNKNOWN_STALE')
        for field in ('visibility', 'biological_detectability', 'overall_visual_signal', 'temporal_visual_signal'):
            self.assertEqual(target[field], 'UNKNOWN')
        self.assertFalse(target['negative_event_label_allowed'])

    def test_cab3_compatibility_requires_healthy_already_expired_prior_unknown(self):
        now = guard.stamp('2026-10-19T04:55:12Z')
        for defect in ('failed_metadata', 'visible', 'fresh_prior_issue'):
            with self.subTest(defect=defect):
                self.owner_expired_review_fixture(now)
                d = self.f.read(binding.SNAPSHOT)
                row = next(r for r in d['input_rows'] if r['source'] == builder.CAMERA)
                target = next(r for r in row['camera_health']['private_cameras'] if r['camera_id'] == 'pcl_e2_back_deck')
                if defect == 'failed_metadata':
                    target['upstream_metadata_pass'] = False
                elif defect == 'visible':
                    target['visibility'] = 'poor'
                else:
                    d['snapshot_time_ct'] = '2026-10-18T22:20:00-05:00'
                    d['reconciliation']['as_of_utc'] = '2026-10-19T03:20:00+00:00'
                self.f.write(binding.SNAPSHOT, d)
                self.f.write(binding.FORECAST, binding.project(builder.encode(d)))
                self.commit('invalid historical owner shape ' + defect)
                self.assert_review_failure_keeps_pair(now)

    def test_pr111_fresh_or_freshness_boundary_review_is_not_reused(self):
        for now in (guard.stamp('2026-10-19T03:20:00Z'),
                    guard.stamp('2026-10-19T04:07:16.809571Z')):
            with self.subTest(now=now):
                self.reviewed_camera_fixture(now)
                self.assert_review_failure_keeps_pair(now, 'fresh or failed camera')

    def test_pr111_one_millisecond_after_expiry_keeps_all_visual_fields_unknown(self):
        now = guard.stamp('2026-10-19T04:07:16.810571Z')
        review = self.reviewed_camera_fixture(now)
        snapshot, _ = self.reconcile(now)
        camera_row = next(r for r in snapshot['input_rows'] if r['source'] == builder.CAMERA)
        target = next(r for r in camera_row['camera_health']['private_cameras'] if r['camera_id'] == review['camera_id'])
        self.assertEqual(target['age_minutes'], 60.0)  # Display rounding is not admission.
        self.assertEqual(target['admitted_status'], 'UNKNOWN_STALE')
        for field in ('visibility', 'biological_detectability', 'overall_visual_signal', 'temporal_visual_signal'):
            self.assertEqual(target[field], 'UNKNOWN')
        self.assertEqual(snapshot['manual_event_review'], review)
        self.assertFalse(target['negative_event_label_allowed'])

    def test_pr111_changed_camera_evidence_still_requires_review_after_expiry(self):
        now = guard.stamp('2026-10-19T04:32:41Z')
        for defect in ('image', 'other_image', 'vision', 'cycle', 'shot', 'registry', 'unbound'):
            with self.subTest(defect=defect):
                self.reviewed_camera_fixture(now)
                if defect in ('image', 'other_image'):
                    name = ('pcl_e2_back_deck' if defect == 'image' else 'montrose_shoreline') + '.jpg'
                    raw = bytearray((self.root/name).read_bytes())
                    raw[len(raw)//2] ^= 1  # same-size JPEG markers retained
                    self.f.write(name, bytes(raw))
                elif defect == 'vision':
                    v = self.f.read('vision.json')
                    v['cameras']['pcl_e2_back_deck']['activity_changed_across_frames'] = 'yes'
                    self.f.write('vision.json', v)
                elif defect == 'cycle':
                    for name in ('status.json', 'burst_status.json', 'vision.json'):
                        d = self.f.read(name)
                        d['capture_time_ct'] = (guard.stamp(d['capture_time_ct']) - timedelta(seconds=1)).isoformat()
                        self.f.write(name, d)
                elif defect == 'shot':
                    for name in ('burst_status.json', 'vision.json'):
                        d = self.f.read(name)
                        shots = d['cameras']['pcl_e2_back_deck']['shots' if name == 'burst_status.json' else 'burst_shots']
                        for shot in shots:
                            shot['timestamp_ct'] = (guard.stamp(shot['timestamp_ct']) + timedelta(seconds=1)).isoformat()
                        self.f.write(name, d)
                    d = self.f.read('status.json')
                    d['cameras']['pcl_e2_back_deck']['timestamp_ct'] = shots[-1]['timestamp_ct']
                    self.f.write('status.json', d)
                elif defect == 'registry':
                    d = self.f.read('model_data/camera_sources.json')
                    d['cameras'][0]['shoreline_cell'] = 'changed geometry'
                    self.f.write('model_data/camera_sources.json', d)
                else:
                    d = self.f.read(binding.SNAPSHOT)
                    d['reconciliation']['source_provenance'].pop('vision.json')
                    self.f.write(binding.SNAPSHOT, d)
                    self.f.write(binding.FORECAST, binding.project(builder.encode(d)))
                self.commit('changed camera evidence ' + defect)
                self.assert_review_failure_keeps_pair(now)

    def test_pr111_missing_or_changed_historical_decision_stops(self):
        now = guard.stamp('2026-10-19T04:32:41Z')
        for defect in ('missing', 'decision', 'alert', 'subject', 'row', 'active_event'):
            with self.subTest(defect=defect):
                self.reviewed_camera_fixture(now)
                d = self.f.read(binding.SNAPSHOT)
                if defect == 'missing':
                    d.pop('manual_event_review')
                elif defect == 'decision':
                    d['manual_event_review']['admitted_event_status'] = 'EVENT_EVIDENCE'
                elif defect == 'alert':
                    d['manual_event_review']['probability_or_alert_change'] = True
                elif defect == 'subject':
                    d['manual_event_review']['camera_id'] = 'montrose_shoreline'
                elif defect == 'row':
                    row = next(r for r in d['input_rows'] if r['source'] == builder.CAMERA)
                    next(r for r in row['camera_health']['private_cameras'] if r['camera_id'] == 'pcl_e2_back_deck')['overall_visual_signal'] = 'none'
                else:
                    d['alert_gates']['direct_event_evidence_present'] = True
                    d['alert_gates']['notification_suppressed'] = False
                    d['notification_condition_met'] = True
                self.f.write(binding.SNAPSHOT, d)
                self.f.write(binding.FORECAST, binding.project(builder.encode(d)))
                self.commit('invalid historical review ' + defect)
                self.assert_review_failure_keeps_pair(now)

    def test_pr111_review_does_not_hide_parser_or_integrity_failures(self):
        now = guard.stamp('2026-10-19T04:32:41Z')
        for defect in ('json', 'jpeg', 'size', 'burst', 'weather_hash', 'weather_parser'):
            with self.subTest(defect=defect):
                self.reviewed_camera_fixture(now)
                if defect == 'json':
                    self.f.write('vision.json', b'invalid JSON')
                elif defect in ('jpeg', 'size'):
                    p = 'pcl_e2_back_deck.jpg'
                    raw = (self.root/p).read_bytes()
                    self.f.write(p, b'bad' + raw[3:] if defect == 'jpeg' else raw + b'bad')
                elif defect == 'burst':
                    d = self.f.read('burst_status.json')
                    d['cameras']['pcl_e2_back_deck']['shots'].pop()
                    self.f.write('burst_status.json', d)
                elif defect == 'weather_hash':
                    d = self.f.read('model_data/asos_weather_manifest.json')
                    d['normalized_sha256'] = '0' * 64
                    self.f.write('model_data/asos_weather_manifest.json', d)
                else:
                    p = 'model_data/asos_weather_normalized.json'
                    d = self.f.read(p)
                    d[0]['value'] = 199
                    self.f.write(p, d)
                    m = self.f.read('model_data/asos_weather_manifest.json')
                    m['normalized_sha256'] = guard.digest((self.root/p).read_bytes())
                    self.f.write('model_data/asos_weather_manifest.json', m)
                self.commit('corrupt evidence ' + defect)
                self.assert_review_failure_keeps_pair(now, '')

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

    def test_preforecast_gate_holds_pair_without_touching_repository(self):
        before = [(self.root / path).read_bytes() for path in publisher.OUTPUTS]
        with patch.object(publisher, 'git') as git_call:
            result = publisher.publish(self.root, as_of='2026-10-02T20:59:59-05:00')
        self.assertEqual(result['status'], 'staged_preforecast_gate')
        self.assertEqual(result['attempts'], 0)
        git_call.assert_not_called()
        self.assertEqual([(self.root / path).read_bytes() for path in publisher.OUTPUTS], before)

    def test_preforecast_gate_central_time_boundaries(self):
        for stamp, expected in (
            ('2026-10-02T16:59:59-05:00', False),
            ('2026-10-02T17:00:00-05:00', True),
            ('2026-10-02T20:59:59-05:00', True),
            ('2026-10-02T21:00:00-05:00', False),
            ('2026-12-02T23:00:00Z', True),  # 17:00 CST, proving DST-safe conversion.
        ):
            with self.subTest(stamp=stamp):
                self.assertEqual(publisher.in_preforecast_staging(stamp), expected)
        with self.assertRaisesRegex(ValueError, 'UTC offset'):
            publisher.in_preforecast_staging('2026-10-02T17:00:00')

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

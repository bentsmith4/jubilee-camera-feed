"""Offline regression tests. No credentials, camera calls or external network."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
import audit_sensing as camera
import backtest_water_quality as backtest
import ingest_river_forcing as river

NOW = datetime(2026, 9, 6, 20, 10, tzinfo=timezone.utc)

class CameraTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = {'cameras': [{'camera_id': 'test', 'access': 'owner_google',
            'site_group': 'one_site', 'shoreline_cell': 'Montrose',
            'configuration_state': 'existing_runtime_expected'}]}
        capture = (NOW - timedelta(minutes=2)).isoformat()
        times = [(NOW - timedelta(seconds=100 - i * 10)).isoformat() for i in range(3)]
        self.status = {'capture_time_ct': capture, 'cameras': {'test': {
            'ok': True, 'timestamp_ct': times[-1], 'bytes': 4}}}
        self.burst = {'capture_time_ct': capture, 'cameras': {'test': {'ok': True,
            'shots': [{'timestamp_ct': t, 'file': 'test_' + str(i) + '.jpg', 'bytes': 4}
                      for i, t in enumerate(times)]}}}
        self.vision = {'capture_time_ct': capture, 'cameras': {'test': {'status': 'ok'}}}
        (self.root / 'test.jpg').write_bytes(b'test')
        for i in range(3):
            (self.root / ('test_' + str(i) + '.jpg')).write_bytes(b'test')
    def tearDown(self):
        self.tmp.cleanup()
    def result(self):
        return camera.audit(self.registry, self.status, self.burst, self.vision, self.root, NOW)
    def test_valid_metadata(self):
        self.assertEqual(self.result()['private_metadata_pass'], 1)
    def test_missing_camera_is_not_silently_removed(self):
        self.status['cameras'] = {}
        self.assertIn('MISSING_EXPECTED_CAMERA', self.result()['private_cameras'][0]['issues'])
    def test_failed_camera(self):
        self.status['cameras']['test']['ok'] = False
        self.assertIn('CAPTURE_FAILED', self.result()['private_cameras'][0]['issues'])
    def test_stale_image(self):
        self.status['cameras']['test']['timestamp_ct'] = (NOW - timedelta(hours=2)).isoformat()
        self.assertIn('STALE', self.result()['private_cameras'][0]['issues'])
    def test_future_time(self):
        self.status['cameras']['test']['timestamp_ct'] = (NOW + timedelta(minutes=2)).isoformat()
        self.assertIn('FUTURE_TIMESTAMP', self.result()['private_cameras'][0]['issues'])
    def test_naive_time_rejected(self):
        self.status['cameras']['test']['timestamp_ct'] = '2026-09-06T20:10:00'
        self.assertIn('MISSING_OFFSET_AWARE_TIMESTAMP', self.result()['private_cameras'][0]['issues'])
    def test_capture_alignment(self):
        self.vision['capture_time_ct'] = NOW.isoformat()
        self.assertIn('CAPTURE_BURST_VISION_MISMATCH', self.result()['private_cameras'][0]['issues'])
    def test_one_second_spacing_rejected(self):
        for i, shot in enumerate(self.burst['cameras']['test']['shots']):
            shot['timestamp_ct'] = (NOW - timedelta(seconds=82 - i)).isoformat()
        self.assertIn('INVALID_OR_MISSING_TEMPORAL_BURST', self.result()['private_cameras'][0]['issues'])
    def test_missing_raw_not_claimed_archived(self):
        (self.root / 'test_0.jpg').unlink()
        self.assertEqual(self.result()['private_cameras'][0]['raw_archive_verification'], 'NOT_VERIFIED')
    def test_missing_human_fields_visible(self):
        self.assertEqual(len(self.result()['private_cameras'][0]['missing_human_sensor_fields']), 6)
    def test_no_detection_is_not_non_event(self):
        self.assertFalse(self.result()['private_cameras'][0]['negative_event_label_allowed'])
    def test_path_traversal_rejected(self):
        self.assertIsNone(camera.safe_file(self.root, '../outside.jpg'))
    def test_size_mismatch(self):
        self.status['cameras']['test']['bytes'] = 999
        self.assertIn('LATEST_IMAGE_MISSING_OR_SIZE_MISMATCH', self.result()['private_cameras'][0]['issues'])

class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.events = {'events': [{'event_id': 'e', 'classification': 'confirmed_jubilee',
                                  'event_date_ct': '2026-08-30'}]}
        self.row = {'source_id': 'test', 'station_id': 's', 'sample_date': '2026-08-29',
                    'sample_time': '07:00', 'parameter': 'Enterococcus', 'value': '10',
                    'unit': 'MPN/100mL', 'method': 'm'}
    def test_same_day_excluded(self):
        row = {**self.row, 'sample_date': '2026-08-30'}
        result = backtest.analyze([row], self.events)
        self.assertEqual(result['unique_event_linked_observations'], 0)
        self.assertEqual(result['same_day_event_sample_pairs_excluded'], 1)
    def test_unique_counts_not_lag_memberships(self):
        result = backtest.analyze([self.row], self.events)
        self.assertEqual(result['unique_event_linked_observations'], 1)
        self.assertEqual(result['event_linked_observations_across_tests'], 4)
    def test_dedup(self):
        result = backtest.analyze([self.row, self.row], self.events)
        self.assertEqual(result['duplicate_rows_excluded'], 1)
        self.assertEqual(result['unique_event_linked_observations'], 1)
    def test_nan_excluded(self):
        result = backtest.analyze([{**self.row, 'value': 'nan'}], self.events)
        self.assertEqual(result['input_unique_numeric_rows'], 0)
    def test_censored_excluded(self):
        result = backtest.analyze([{**self.row, 'detection_condition': 'Not Detected'}], self.events)
        self.assertEqual(result['input_unique_numeric_rows'], 0)
    def test_no_automatic_promotion(self):
        self.assertFalse(backtest.analyze([self.row], self.events)['sufficient_for_production_promotion'])
    def test_geographic_mapping_required(self):
        result = backtest.analyze([self.row, {**self.row, 'sample_date': '2025-08-01'}], self.events)
        self.assertEqual(result['results'], [])
        self.assertEqual(result['verified_matched_non_event_count'], 0)
    def test_mapped_background_not_negative(self):
        self.events['events'][0]['analysis_station_ids'] = ['s']
        result = backtest.analyze([self.row, {**self.row, 'sample_date': '2025-08-01'}], self.events)
        self.assertEqual(len(result['results']), 4)
        self.assertEqual(result['results'][0]['predictive_validity'], 'NOT_ESTABLISHED')
    def test_adjacent_events_one_temporal_block(self):
        self.events['events'].append({'event_id': 'e2', 'classification': 'confirmed_jubilee',
                                      'event_date_ct': '2026-08-29'})
        self.assertEqual(backtest.analyze([], self.events)['conservative_temporal_validation_blocks'], 1)
    def test_units_separated(self):
        self.events['events'][0]['analysis_station_ids'] = ['s']
        different = {**self.row, 'sample_date': '2025-08-01', 'unit': 'cfu/100mL'}
        self.assertEqual(backtest.analyze([self.row, different], self.events)['results'], [])

class RiverTests(unittest.TestCase):
    def test_constant_flow_volume(self):
        end = NOW + timedelta(hours=1)
        result = river.integrate([(NOW, 100), (end, 100)], NOW, end)
        self.assertAlmostEqual(result['observed_interval_volume_m3'], 100 * 3600 * river.CFS_TO_CMS, places=2)
        self.assertEqual(result['coverage_fraction'], 1)
    def test_gap_not_filled(self):
        end = NOW + timedelta(hours=3)
        result = river.integrate([(NOW, 100), (end, 100)], NOW, end)
        self.assertEqual(result['covered_seconds'], 0)
    def test_edges_not_extrapolated(self):
        points = [(NOW + timedelta(minutes=15), 100), (NOW + timedelta(minutes=45), 100)]
        result = river.integrate(points, NOW, NOW + timedelta(hours=1))
        self.assertEqual(result['coverage_fraction'], 0.5)
        self.assertFalse(result['eligible_for_research_feature'])
    def test_nonfinite_rejected(self):
        self.assertIsNone(river.finite('inf'))
    def test_invalid_schema_rejected(self):
        with self.assertRaises(ValueError):
            river.normalize({'error': 'upstream'}, NOW, 'test')
    def test_normalize_qualifiers_and_nodata(self):
        doc = {'value': {'timeSeries': [{'name': 'flow',
            'sourceInfo': {'siteCode': [{'value': '02428400'}], 'siteName': 'Claiborne'},
            'variable': {'variableCode': [{'value': '00060'}], 'unit': {'unitCode': 'ft3/s'}, 'noDataValue': -999999},
            'values': [{'value': [
                {'dateTime': NOW.isoformat(), 'value': '100', 'qualifiers': ['P']},
                {'dateTime': NOW.isoformat(), 'value': '-999999', 'qualifiers': ['P']}]}]}]}}
        rows = river.normalize(doc, NOW, 'test')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['qualifiers'], 'P')
        self.assertEqual(rows[0]['production_weight'], 0)
    def test_downstream_not_added_to_pool(self):
        rows = []
        for station in ('02469761', '02469762'):
            rows.append({'station_id': station, 'series_id': station + ':00060', 'parameter_code': '00060',
                         'unit': 'ft3/s', 'observed_at_utc': NOW.isoformat(), 'value': 100,
                         'qualifiers': 'P', 'research_qc_eligible': True})
        result = river.summarize(rows, NOW)
        self.assertEqual(len(result), 2)
        self.assertEqual({x['station_id'] for x in result}, {'02469761', '02469762'})

if __name__ == '__main__':
    unittest.main()

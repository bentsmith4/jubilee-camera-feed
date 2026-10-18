"""NOAA observation admission; synthetic cases plus a hashed public API fixture."""
import copy
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
import ingest_noaa_water_level as noaa
import reconcile_source_registry as registry
import stage_sensing_outputs as publication

NOW = datetime(2026, 10, 17, 17, 20, tzinfo=timezone.utc)
URL = noaa.request_url(NOW)
FIXTURES = ROOT / 'tests/fixtures/noaa_water_level'


def report(age=8, **updates):
    return {'t': (NOW - timedelta(minutes=age)).strftime('%Y-%m-%d %H:%M'),
            'v': '0.095', 's': '0.079', 'f': '1,0,0,0', 'q': 'p', **updates}


def payload(*rows):
    return {'metadata': {'id': '8735180', 'name': 'Dauphin Island',
                         'lat': '30.2500', 'lon': '-88.0750'},
            'data': list(rows)}


class WaterLevelTests(unittest.TestCase):
    def rows(self, *reports):
        return noaa.normalize(payload(*reports), NOW, URL)[0]

    def snapshot(self, *reports, at=NOW):
        return noaa.current_snapshot(self.rows(*reports), at)

    def ingest(self, directory, document=None, at=NOW):
        document = payload(report()) if document is None else document
        return noaa.ingest(directory, lambda url: json.dumps(document).encode(), lambda: at)

    def test_measured_identity_units_utc_and_required_fields(self):
        rows = self.rows(report())
        required = json.loads((noaa.HERE / 'sensor_contract.json').read_text())['required_fields']
        row = rows[0]
        self.assertTrue(set(required) <= row.keys())
        for key, value in {'sensor_id': '8735180', 'unit': 'm', 'vertical_reference': 'MLLW',
                           'source_class': 'noaa_observed_water_level', 'production_weight': 0,
                           'is_direct_local_bottom_measurement': False, 'depth_m': None,
                           'received_at_utc': None, 'available_at': NOW.isoformat()}.items():
            self.assertEqual(row[key], value)
        self.assertEqual(noaa.current_snapshot(rows, NOW)['value'], .095)
        self.assertEqual(row['source_flag_names'][0], 'outlier_sample_count')

    def test_freshness_boundary_and_delayed_consumer(self):
        rows = self.rows(report(age=60))
        self.assertEqual(noaa.current_snapshot(rows, NOW)['value_status'], 'KNOWN')
        late = noaa.current_snapshot(rows, NOW + timedelta(seconds=1))
        self.assertEqual(late['admission_reason'], 'STALE')
        self.assertIsNone(late['value'])

    def test_preliminary_outlier_count_is_not_verified_inferred_flag(self):
        self.assertEqual(self.snapshot(report(f='12,0,0,0'))['value_status'], 'KNOWN')
        self.assertEqual(self.snapshot(report(q='v', f='0,0,0,0'))['value_status'], 'KNOWN')
        for flags in ('1,0,0,0', '2,0,0,0'):
            self.assertEqual(self.snapshot(report(q='v', f=flags))['value_status'], 'UNKNOWN')
        self.assertEqual(self.snapshot(report(q='v'))['admission_reason'], 'SOURCE_INFERRED_HEIGHT')

    def test_flags_quality_and_sigma_fail_closed(self):
        for updates in ({'f': '0,1,0,0'}, {'f': '0,0,1,0'}, {'f': '0,0,0,1'},
                        {'f': '0,2,0,0'}, {'f': '0,0,0'}, {'f': ''}, {'f': None},
                        {'q': 'unknown'}, {'s': None}, {'s': '-1'}, {'s': 'NaN'}):
            with self.subTest(updates=updates):
                current = self.snapshot(report(**updates))
                self.assertEqual(current['value_status'], 'UNKNOWN')
                self.assertIsNone(current['value'])

    def test_missing_nonfinite_boolean_value_never_becomes_zero(self):
        for value in (None, '', '  ', True, 'NaN', 'Infinity', float('nan'), float('inf')):
            with self.subTest(value=value):
                self.assertIsNone(self.snapshot(report(v=value))['value'])
        self.assertEqual(self.snapshot(report(v='0'))['value'], 0.0)
        self.assertEqual(self.snapshot(report(v='-0.1'))['value'], -.1)

    def test_newest_bad_future_or_conflicting_row_never_backfills(self):
        for newest in (report(age=2, v=''), report(age=-1), report(age=2, f='0,1,0,0')):
            self.assertEqual(self.snapshot(report(age=20), newest)['value_status'], 'UNKNOWN')
        same = report()
        self.assertEqual(len(self.rows(same, same)), 1)
        self.assertEqual(self.snapshot(same, report(v='.096'))['admission_reason'],
                         'CONFLICTING_DUPLICATE_TIMESTAMP')
        self.assertEqual(self.snapshot(same, report(v='.096'))['value_status'], 'UNKNOWN')

    def test_station_geometry_and_request_product_are_strict(self):
        for key, value in (('id', '8733821'), ('name', None), ('name', 'Point Clear'),
                           ('lat', '30.5'), ('lon', 'NaN')):
            document = payload(report()); document['metadata'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                noaa.normalize(document, NOW, URL)
        for key, value in (('station=8735180', 'station=8733821'),
                           ('product=water_level', 'product=predictions'), ('datum=MLLW', 'datum=MSL'),
                           ('units=metric', 'units=english'), ('time_zone=gmt', 'time_zone=lst_ldt')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                noaa.normalize(payload(report()), NOW, URL.replace(key, value))
        with self.assertRaises(ValueError):
            noaa.normalize(payload(report()), NOW, URL + '&station=8733821')

    def test_invalid_time_and_unbounded_rows_invalidate_run(self):
        for document in (payload(report(), report(t='bad')), payload(report(), report(t='2026-02-30 17:12')),
                         payload(*([report()] * 101)), {'predictions': [report()]}, [],
                         {'metadata': payload()['metadata'], 'data': [None]}):
            with self.subTest(document=str(document)[:80]), tempfile.TemporaryDirectory() as tmp:
                manifest = self.ingest(tmp, document)
                self.assertEqual(manifest['status'], 'failed')
                self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')

    def test_empty_explicit_no_data_and_unexpected_api_errors(self):
        for document, expected in ((payload(), 'empty'),
                                   ({'error': {'message': 'No data was found. Try a different date.'}}, 'empty'),
                                   ({'error': {'message': 'Invalid datum'}}, 'failed')):
            with self.subTest(document=document), tempfile.TemporaryDirectory() as tmp:
                manifest = self.ingest(tmp, document)
                self.assertEqual(manifest['status'], expected)
                self.assertIsNone(noaa.load_current(tmp, NOW)['value'])

    def test_raw_archive_hash_manifest_pair_and_first_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest = self.ingest(directory)
            raw = gzip.decompress((directory / manifest['raw_path']).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['raw_sha256'])
            self.assertEqual(noaa.load_current(directory, NOW)['value_status'], 'KNOWN')
            self.ingest(directory, at=NOW + timedelta(minutes=2))
            _, rows = noaa.read_pair(directory)
            self.assertEqual(rows[0]['available_at'], NOW.isoformat())
            self.assertEqual(rows[0]['ingested_at'], (NOW + timedelta(minutes=2)).isoformat())
            self.assertEqual(noaa.load_current(directory, NOW)['value_status'], 'UNKNOWN')
            self.assertEqual(noaa.load_current(directory, NOW + timedelta(minutes=61))['admission_reason'], 'STALE')
            self.ingest(directory, payload(report(v='.096')), at=NOW + timedelta(minutes=3))
            _, rows = noaa.read_pair(directory)
            self.assertEqual(rows[0]['available_at'], (NOW + timedelta(minutes=3)).isoformat())

    def test_outage_and_interrupted_run_invalidate_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.ingest(tmp)
            def outage(url):
                self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')
                raise urllib.error.URLError('offline')
            result = noaa.ingest(tmp, outage, lambda: NOW)
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')
            self.ingest(tmp)
            with self.assertRaises(KeyboardInterrupt):
                noaa.ingest(tmp, lambda url: (_ for _ in ()).throw(KeyboardInterrupt()), lambda: NOW)
            self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')

    def test_request_errors_differ_from_transient_outages(self):
        for code, expected in ((400, 'failed'), (404, 'failed'), (422, 'failed'),
                               (429, 'unavailable'), (503, 'unavailable')):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                def failure(url):
                    raise urllib.error.HTTPError(url, code, 'error', {}, None)
                result = noaa.ingest(tmp, failure, lambda: NOW)
                self.assertEqual(result['status'], expected)

    def test_nonfinite_json_numbers_fail_before_retained_field_serialization(self):
        for field in ('v', 'q', 'f', 's'):
            for value in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                    manifest = self.ingest(tmp, payload(report(**{field: value})))
                    self.assertEqual(manifest['status'], 'failed')
                    self.assertEqual(manifest['error_type'], 'ValueError')
                    self.assertIn('raw_sha256', manifest)
                    self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')
        for field in ('v', 'q', 'f', 's'):
            for value in ('1e999', '-1e999'):
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                    raw = json.dumps(payload(report(**{field: 'OVERFLOW'}))).replace('"OVERFLOW"', value).encode()
                    manifest = noaa.ingest(tmp, lambda url: raw, lambda: NOW)
                    self.assertEqual(manifest['status'], 'failed')
                    self.assertEqual(noaa.load_current(tmp, NOW)['value_status'], 'UNKNOWN')

    def test_missing_legacy_malformed_and_tampered_products_are_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.assertEqual(noaa.load_current(directory, NOW)['value_status'], 'UNKNOWN')
            self.ingest(directory)
            (directory / noaa.SNAPSHOT).write_text('{"value_status":"KNOWN","value":999}')
            self.assertEqual(noaa.load_current(directory, NOW)['value'], .095)
            (directory / noaa.NORMALIZED).write_text('[]')
            self.assertEqual(noaa.load_current(directory, NOW)['value_status'], 'UNKNOWN')
            self.ingest(directory)
            manifest, rows = noaa.read_pair(directory)
            for key, value in (('vertical_reference', 'MSL'), ('unit', 'ft'), ('source_id', 'other'),
                               ('production_weight', 1), ('latitude', 30.5), ('available_at', 'bad'),
                               ('source_flags', '0,1,0,0'), ('value_status', 'UNKNOWN')):
                altered = copy.deepcopy(rows); altered[0][key] = value
                self.assertEqual(noaa.current_snapshot(altered, NOW)['value_status'], 'UNKNOWN')
            manifest['source_url'] = URL.replace('MLLW', 'MSL')
            noaa.write_json(directory / noaa.MANIFEST, manifest)
            self.assertEqual(noaa.load_current(directory, NOW)['value_status'], 'UNKNOWN')

    def test_non_utc_offset_is_normalized_and_naive_time_rejected(self):
        at = NOW.astimezone(timezone(timedelta(hours=-5)))
        self.assertEqual(noaa.current_snapshot(self.rows(report()), at)['evaluated_at_utc'], NOW.isoformat())
        self.assertEqual(noaa.request_url(at), URL)
        for action in (lambda: noaa.current_snapshot([], NOW.replace(tzinfo=None)),
                       lambda: noaa.request_url(NOW.replace(tzinfo=None)),
                       lambda: noaa.load_current('/missing', NOW.replace(tzinfo=None))):
            with self.assertRaises(ValueError):
                action()

    def test_backward_clock_fails_closed(self):
        for times in ((NOW, NOW - timedelta(seconds=1), NOW),
                      (NOW, NOW, NOW - timedelta(seconds=1))):
            with tempfile.TemporaryDirectory() as tmp:
                clock = iter(times)
                manifest = noaa.ingest(tmp, lambda url: json.dumps(payload(report())).encode(), lambda: next(clock))
                self.assertEqual(manifest['status'], 'failed')
                self.assertIsNone(noaa.load_current(tmp, NOW)['value'])

    def test_live_fixture_hash_geometry_normalization_and_replay(self):
        receipt = json.loads((FIXTURES / 'retrieval_receipt.json').read_text())
        raw = (FIXTURES / 'observed_8735180_20261017.json').read_bytes()
        metadata = (FIXTURES / 'station_8735180.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt['raw_sha256'])
        self.assertEqual(hashlib.sha256(metadata).hexdigest(), receipt['metadata_sha256'])
        station = json.loads(metadata)['stations'][0]
        self.assertEqual(station['id'], '8735180')
        self.assertEqual(station['lat'], 30.25)
        self.assertEqual(station['lng'], -88.075)
        at = noaa.utc(receipt['retrieved_at_utc'])
        rows, rejected = noaa.normalize(json.loads(raw), at, receipt['source_url'])
        self.assertEqual(len(rows), 59)
        self.assertFalse(rejected)
        snapshot = noaa.current_snapshot(rows, at)
        self.assertEqual(snapshot['observed_at_utc'], '2026-10-17T17:12:00+00:00')
        self.assertEqual(snapshot['value'], .095)
        self.assertEqual(snapshot['source_flags'], '1,0,0,0')
        self.assertEqual(noaa.current_snapshot(rows, at + timedelta(hours=2))['value_status'], 'UNKNOWN')
        with tempfile.TemporaryDirectory() as tmp:
            manifest = noaa.ingest(tmp, lambda url: raw, lambda: at)
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(manifest['raw_sha256'], receipt['raw_sha256'])
            self.assertEqual(noaa.load_current(tmp, at)['value'], .095)

    def test_registry_missing_product_leaves_existing_noaa_metadata_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); target = directory / 'registry.json'
            base = json.loads((ROOT / 'model_data/ongoing_source_registry_20260906.json').read_text())
            before = next(r for r in base['sources'] if r['source_id'] == noaa.SOURCE_ID)
            target.write_text(json.dumps(base))
            with patch.object(registry, 'HERE', directory), patch.object(registry, 'REGISTRY', target), patch('builtins.print'):
                registry.main()
            after = next(r for r in json.loads(target.read_text())['sources'] if r['source_id'] == noaa.SOURCE_ID)
            self.assertEqual(after, before)
            self.ingest(directory)
            with patch.object(registry, 'HERE', directory), patch.object(registry, 'REGISTRY', target), patch('builtins.print'):
                registry.main()
            after = next(r for r in json.loads(target.read_text())['sources'] if r['source_id'] == noaa.SOURCE_ID)
            self.assertEqual(after['normalized_rows'], 1)
            self.assertEqual(after['production_weight'], 0)
            self.assertEqual(after['ingestion_status'], 'complete')
            self.assertEqual(after['location'], before['location'])
            self.assertEqual(after['production_role'], before['production_role'])

    def test_workflow_preserves_schedule_and_producer_gates(self):
        workflow = (ROOT / '.github/workflows/asos_weather.yml').read_text()
        self.assertIn("cron: '7 * * * *'", workflow)
        sensing = (ROOT / '.github/workflows/sensing_quality.yml').read_text()
        self.assertNotIn('python model_data/ingest_noaa_water_level.py', sensing)
        self.assertIn('id: noaa_water_level', workflow)
        self.assertIn("steps.noaa_water_level.outcome == 'failure'", workflow)
        self.assertIn('python model_data/ingest_noaa_water_level.py', workflow)
        for name in (noaa.MANIFEST, noaa.NORMALIZED, noaa.SNAPSHOT):
            self.assertIn(name, workflow)
        expected = {'model_data/' + name for name in (noaa.MANIFEST, noaa.NORMALIZED, noaa.SNAPSHOT, 'public_archive/coops')}
        self.assertEqual(set(publication.publication_paths({'noaa_water_level': {'outcome': 'success'}}, 'main')), expected)
        self.assertFalse(publication.publication_paths({'noaa_water_level': {'outcome': 'failure', 'conclusion': 'success'}}, 'main'))


class FetchTests(unittest.TestCase):
    def response(self, body):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return body[:size]
        return Response()

    def test_transient_retries_are_bounded(self):
        busy = urllib.error.HTTPError(URL, 429, 'busy', {}, None)
        with patch.object(noaa.urllib.request, 'urlopen', side_effect=[busy, self.response(b'{}')]) as fetch, patch.object(noaa.time, 'sleep') as sleep:
            self.assertEqual(noaa.fetch(URL), b'{}')
            self.assertEqual(fetch.call_count, 2)
            sleep.assert_called_once_with(1)
        with patch.object(noaa.urllib.request, 'urlopen', side_effect=TimeoutError) as fetch, patch.object(noaa.time, 'sleep'):
            with self.assertRaises(TimeoutError): noaa.fetch(URL)
            self.assertEqual(fetch.call_count, 3)

    def test_bound_and_nonretryable_request_error(self):
        with patch.object(noaa.urllib.request, 'urlopen', return_value=self.response(b'x' * (noaa.MAX_BYTES + 1))):
            with self.assertRaises(ValueError): noaa.fetch(URL)
        invalid = urllib.error.HTTPError(URL, 400, 'invalid', {}, None)
        with patch.object(noaa.urllib.request, 'urlopen', side_effect=invalid) as fetch:
            with self.assertRaises(urllib.error.HTTPError): noaa.fetch(URL)
            self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()

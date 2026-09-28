"""Offline ASOS admission tests. Fixtures are synthetic, not weather evidence."""
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
import ingest_asos_weather as asos
import build_readiness

NOW = datetime(2026, 9, 28, 11, 44, 12, tzinfo=timezone.utc)


def report(station='KBFM', age=51.2, **updates):
    name, lat, lon = asos.STATIONS[station]
    observed = NOW - timedelta(minutes=age)
    return dict(icaoId=station, obsTime=int(observed.timestamp()),
                receiptTime=(observed + timedelta(minutes=2)).isoformat(),
                reportTime=observed.replace(minute=0).isoformat(),
                metarType='METAR', rawOb=f'METAR {station} 281053Z 09005KT 10SM CLR 26/22 A2990 RMK AO2',
                lat=lat, lon=lon, name=name, wspd=5, wdir=90, temp=26, dewp=22,
                **updates)


def parameter(snapshot, name, station='KBFM'):
    return snapshot['stations'][station]['parameters'][name]


class ASOSWeatherTests(unittest.TestCase):
    def snapshot(self, reports, at=NOW):
        rows, _ = asos.normalize(reports, NOW)
        return asos.current_snapshot(rows, at)

    def test_contract_and_timestamp_semantics(self):
        source = report()
        rows, _ = asos.normalize([source], NOW)
        required = json.loads((asos.HERE / 'sensor_contract.json').read_text())['required_fields']
        for row in rows:
            self.assertTrue(set(required) <= row.keys())
            self.assertEqual(row['source_class'], 'asos_observation')
            self.assertEqual(row['freshness_minutes'], 90)
            self.assertEqual(row['production_weight'], 0)
            self.assertFalse(row['is_direct_local_bottom_measurement'])
            self.assertEqual(row['observed_at_utc'], asos.observation_time(source).isoformat())
            self.assertEqual(row['received_at_utc'], source['receiptTime'])
            self.assertEqual(row['available_at'], NOW.isoformat())
        self.assertEqual(parameter(asos.current_snapshot(rows, NOW), 'wind_speed')['value'], 5)

    def test_september_27_stale_wind_blank_rain_regression(self):
        snapshot = self.snapshot([report(age=175), report('KMOB', age=172)])
        for station in asos.STATIONS:
            self.assertEqual(parameter(snapshot, 'wind_speed', station)['admission_reason'], 'STALE')
            self.assertIsNone(parameter(snapshot, 'wind_speed', station)['value'])
            self.assertEqual(parameter(snapshot, 'precipitation_1h', station)['value_status'], 'UNKNOWN')

    def test_exact_freshness_boundary_and_delayed_consumer(self):
        rows, _ = asos.normalize([report(age=90)], NOW)
        self.assertEqual(parameter(asos.current_snapshot(rows, NOW), 'wind_speed')['value_status'], 'KNOWN')
        late = asos.current_snapshot(rows, NOW + timedelta(seconds=1))
        self.assertEqual(parameter(late, 'wind_speed')['admission_reason'], 'STALE')

    def test_blank_null_absent_rain_is_unknown_but_zero_is_known(self):
        for missing in (None, '', '  '):
            snapshot = self.snapshot([report(precip=missing)])
            self.assertIsNone(parameter(snapshot, 'precipitation_1h')['value'])
            self.assertEqual(parameter(snapshot, 'precipitation_1h')['value_status'], 'UNKNOWN')
        snapshot = self.snapshot([report(precip=0, pcp3hr=0.15, pcp6hr=0.25, pcp24hr=1.2)])
        for hours, expected in ((1, 0), (3, .15), (6, .25), (24, 1.2)):
            value = parameter(snapshot, f'precipitation_{hours}h')
            self.assertEqual(value['value'], expected)
            self.assertEqual(value['unit'], 'in')
        self.assertEqual(parameter(self.snapshot([report()]), 'precipitation_1h')['value_status'], 'UNKNOWN')

    def test_trace_is_not_zero_or_invented_quantity(self):
        for decoded in (0, .005):
            source = report(precip=decoded)
            source['rawOb'] += ' P0000'
            value = parameter(self.snapshot([source]), 'precipitation_1h')
            self.assertEqual(value['value_status'], 'TRACE')
            self.assertIsNone(value['value'])

    def test_precipitation_sensor_outage_overrides_numeric_value(self):
        for flag in ('PNO', 'PWINO'):
            source = report(precip=0)
            source['rawOb'] += ' ' + flag
            snapshot = self.snapshot([source])
            self.assertEqual(parameter(snapshot, 'precipitation_1h')['value_status'], 'UNKNOWN')
            self.assertEqual(parameter(snapshot, 'wind_speed')['value_status'], 'KNOWN')

    def test_future_and_unavailable_observations_rejected(self):
        future = parameter(self.snapshot([report(age=-2)]), 'wind_speed')
        self.assertEqual(future['value_status'], 'UNKNOWN')
        self.assertIn('FUTURE_OBSERVATION', future['qc_flag'])
        before_fetch = parameter(self.snapshot([report()], at=NOW - timedelta(seconds=1)), 'wind_speed')
        self.assertEqual(before_fetch['admission_reason'], 'NOT_AVAILABLE_AT_ISSUE_TIME')

    def test_receipt_time_not_replaced_by_observation_or_report_time(self):
        for receipt in ('2026-09-28T11:00:00', 'invalid', (NOW+timedelta(minutes=1)).isoformat(), '2026-09-27T00:00:00Z'):
            source = report()
            source['receiptTime'] = receipt
            self.assertEqual(parameter(self.snapshot([source]), 'wind_speed')['value_status'], 'UNKNOWN')
        source = report()
        source.pop('receiptTime')
        source['reportTime'] = (NOW + timedelta(hours=1)).isoformat()
        value = parameter(self.snapshot([source]), 'wind_speed')
        self.assertIsNone(value['received_at_utc'])
        self.assertEqual(value['available_at'], NOW.isoformat())
        self.assertEqual(value['value_status'], 'KNOWN')

    def test_missing_and_invalid_observation_times_are_not_filled(self):
        for observed in (None, '', 'bad', 1e30, True):
            source = report()
            source['obsTime'] = observed
            rows, rejected = asos.normalize([source], NOW)
            self.assertEqual(rows, [])
            self.assertEqual(len(rejected), 1)

    def test_station_and_report_qc(self):
        for field, value in (('rawOb', 'METAR KXYZ 281053Z NIL'), ('metarType', 'TAF'), ('lat', 0), ('lon', None)):
            source = report()
            source[field] = value
            self.assertEqual(parameter(self.snapshot([source]), 'wind_speed')['value_status'], 'UNKNOWN')
        source = report()
        source['rawOb'] += ' $'
        self.assertEqual(parameter(self.snapshot([source]), 'wind_speed')['value_status'], 'UNKNOWN')
        self.assertEqual(self.snapshot([dict(report(), icaoId='KXYZ')])['stations']['KBFM']['status'], 'UNKNOWN')

    def test_variable_and_calm_wind_direction_remain_unknown(self):
        for direction, speed in (('VRB', 5), (0, 0)):
            source = dict(report(), wdir=direction, wspd=speed)
            snapshot = self.snapshot([source])
            self.assertEqual(parameter(snapshot, 'wind_direction')['value_status'], 'UNKNOWN')
            self.assertEqual(parameter(snapshot, 'wind_speed')['value'], speed)

    def test_field_qc_independent_and_nonfinite_rejected(self):
        for invalid in (-1, 9999, 'NaN', 'Infinity', True, 'M'):
            source = dict(report(), wspd=invalid)
            self.assertEqual(parameter(self.snapshot([source]), 'wind_speed')['value_status'], 'UNKNOWN')
        source = dict(report(), dewp=35, wgst=2)
        snapshot = self.snapshot([source])
        self.assertEqual(parameter(snapshot, 'dew_point')['value_status'], 'UNKNOWN')
        self.assertEqual(parameter(snapshot, 'wind_gust')['value_status'], 'UNKNOWN')
        self.assertEqual(parameter(snapshot, 'air_temperature')['value'], 26)

    def test_newest_per_station_and_corrected_report_no_old_field_fill(self):
        older = report(age=70, precip=1)
        latest = report(age=10)
        correction = dict(latest, receiptTime=(NOW-timedelta(minutes=1)).isoformat(), wspd=8)
        snapshot = self.snapshot([correction, older, latest, older, report('KMOB', age=20)])
        self.assertEqual(parameter(snapshot, 'wind_speed')['value'], 8)
        self.assertEqual(parameter(snapshot, 'precipitation_1h')['value_status'], 'UNKNOWN')
        self.assertEqual(parameter(snapshot, 'wind_speed', 'KMOB')['value'], 5)

    def test_duplicate_retrieval_preserves_first_availability_correction_does_not(self):
        source = report()
        first, _ = asos.normalize([source], NOW)
        repeated, _ = asos.normalize([source], NOW+timedelta(minutes=5), first)
        self.assertEqual(repeated[0]['available_at'], NOW.isoformat())
        corrected, _ = asos.normalize([dict(source, wspd=8)], NOW+timedelta(minutes=5), first)
        self.assertEqual(corrected[0]['available_at'], (NOW+timedelta(minutes=5)).isoformat())

    def test_sensor_contract_is_used_at_consumption(self):
        rows, _ = asos.normalize([report()], NOW)
        with patch.object(asos, 'freshness_limit', return_value=30):
            self.assertEqual(parameter(asos.current_snapshot(rows, NOW), 'wind_speed')['admission_reason'], 'STALE')

    def test_ingestion_archives_bytes_and_retrieves_before_timestamp(self):
        payload = json.dumps([report()]).encode()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            ticks = iter([NOW-timedelta(minutes=1), NOW, NOW+timedelta(seconds=1)])
            manifest = asos.ingest(directory, lambda: payload, lambda: next(ticks))
            self.assertEqual(manifest['status'], 'complete')
            self.assertEqual(manifest['raw_sha256'], hashlib.sha256(payload).hexdigest())
            self.assertEqual(gzip.decompress((directory/manifest['raw_path']).read_bytes()), payload)
            snapshot = asos.load_current(directory, NOW+timedelta(seconds=1))
            self.assertEqual(parameter(snapshot, 'wind_speed')['available_at'], NOW.isoformat())

    def test_empty_missing_station_outage_and_malformed_replace_previous_data(self):
        for payload in (b'[]', b'{}', b'<html>error</html>', b'[null]', b'[{"icaoId":"KMOB"}]'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                asos.ingest(directory, lambda: json.dumps([report()]).encode(), lambda: NOW)
                manifest = asos.ingest(directory, lambda: payload, lambda: NOW)
                self.assertEqual(asos.load_current(directory, NOW)['stations']['KBFM']['status'], 'UNKNOWN')
                self.assertEqual(manifest['status'], 'failed' if payload in (b'{}', b'<html>error</html>', b'[null]') else 'complete')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            asos.ingest(directory, lambda: json.dumps([report()]).encode(), lambda: NOW)
            def outage():
                self.assertEqual(asos.load_current(directory, NOW)['stations']['KBFM']['status'], 'UNKNOWN')
                raise urllib.error.URLError('offline')
            self.assertEqual(asos.ingest(directory, outage, lambda: NOW)['status'], 'unavailable')
            self.assertEqual(json.loads((directory/asos.NORMALIZED).read_text()), [])

    def test_manifest_data_pair_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            asos.ingest(directory, lambda: json.dumps([report()]).encode(), lambda: NOW)
            (directory/asos.NORMALIZED).write_text('[]')
            self.assertEqual(asos.load_current(directory, NOW)['stations']['KBFM']['status'], 'UNKNOWN')

    def test_malformed_cache_is_unknown_and_does_not_block_next_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            digest = asos.write_json(directory/asos.NORMALIZED, [None])
            asos.write_json(directory/asos.MANIFEST, {'normalized_sha256': digest, 'status': 'complete'})
            self.assertEqual(asos.load_current(directory, NOW)['stations']['KBFM']['status'], 'UNKNOWN')
            self.assertEqual(asos.ingest(directory, lambda: json.dumps([report()]).encode(), lambda: NOW)['status'], 'complete')

    def test_request_defect_fails_while_upstream_outage_is_unknown(self):
        for code, expected in ((400, 'failed'), (404, 'failed'), (429, 'unavailable'), (503, 'unavailable')):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                def failure():
                    raise urllib.error.HTTPError(asos.URL, code, 'error', {}, None)
                manifest = asos.ingest(Path(tmp), failure, lambda: NOW)
                self.assertEqual(manifest['status'], expected)
                self.assertEqual(manifest['http_status'], code)

    def test_numeric_nan_and_infinity_persist_as_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = dict(report(), wspd=float('nan'), precip=float('inf'))
            manifest = asos.ingest(directory, lambda: json.dumps([source]).encode(), lambda: NOW)
            self.assertEqual(manifest['status'], 'complete')
            snapshot = asos.load_current(directory, NOW)
            self.assertEqual(parameter(snapshot, 'wind_speed')['value_status'], 'UNKNOWN')
            self.assertEqual(parameter(snapshot, 'precipitation_1h')['value_status'], 'UNKNOWN')

    def test_readiness_consumes_weather_and_preserves_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            asos.ingest(directory, lambda: json.dumps([report()]).encode(), lambda: NOW)
            with patch.object(build_readiness, 'HERE', directory), patch('builtins.print'):
                build_readiness.main()
            readiness = json.loads((directory/'upgrade_readiness.json').read_text())
            self.assertIn('asos_observed_weather', readiness)
            self.assertFalse(readiness['forecast_weights_changed'])
            self.assertEqual(readiness['asos_observed_weather']['production_weight'], 0)

    def test_workflow_wires_retrieval_persistence_and_offline_ci(self):
        root = asos.HERE.parent
        workflow = (root/'.github/workflows/sensing_quality.yml').read_text()
        self.assertIn('python model_data/ingest_asos_weather.py', workflow)
        for name in (asos.MANIFEST, asos.NORMALIZED, asos.SNAPSHOT):
            self.assertIn(name, workflow)
        hourly = (root/'.github/workflows/asos_weather.yml').read_text()
        self.assertIn("cron: '7 * * * *'", hourly)
        self.assertIn('jubilee-sensing-quality-${{ github.ref_name }}', hourly)


class ASOSFetchTests(unittest.TestCase):
    def response(self, payload, status=200):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return payload[:size]
        response = Response()
        response.status = status
        return response

    def test_no_content(self):
        with patch.object(asos.urllib.request, 'urlopen', return_value=self.response(b'', 204)):
            self.assertEqual(asos.fetch(), b'[]')

    def test_transient_retries_bounded_and_user_agent(self):
        errors = [urllib.error.HTTPError(asos.URL, 429, 'busy', {}, None), self.response(b'[]')]
        with patch.object(asos.urllib.request, 'urlopen', side_effect=errors) as fetch, patch.object(asos.time, 'sleep') as sleep:
            self.assertEqual(asos.fetch(), b'[]')
            self.assertEqual(fetch.call_count, 2)
            self.assertIn('jubilee-camera-feed', fetch.call_args.args[0].headers['User-agent'])
            sleep.assert_called_once_with(1)
        with patch.object(asos.urllib.request, 'urlopen', side_effect=TimeoutError), patch.object(asos.time, 'sleep') as sleep:
            with self.assertRaises(TimeoutError):
                asos.fetch()
            self.assertEqual(sleep.call_count, 2)

    def test_oversized_response_is_parser_failure(self):
        with patch.object(asos.urllib.request, 'urlopen', return_value=self.response(b'x'*2_000_001)):
            with self.assertRaises(ValueError):
                asos.fetch()


if __name__ == '__main__':
    unittest.main()

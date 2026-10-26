import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from netCDF4 import Dataset, date2num, num2date

from model_data import ngofs2_station_access as access
from model_data import validate_ngofs2_availability as availability

CYCLE = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)


def fixture(cast="nowcast", shift=0, missing_last=False):
    start = CYCLE - timedelta(hours=6) if cast == "nowcast" else CYCLE
    count = 61 if cast == "nowcast" else 481
    times = [start + timedelta(minutes=6*i + shift) for i in range(count - int(missing_last))]
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "station.nc"
        with Dataset(path, "w") as ds:
            ds.title = "NGOFS2"
            ds.createDimension("time", len(times))
            t = ds.createVariable("time", "f8", ("time",))
            t.units = "seconds since 2019-01-01 00:00:00"
            t[:] = date2num(times, t.units)
        return path.read_bytes()


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {} if length is None else {"Content-Length": str(length)}


class StationAccessTests(unittest.TestCase):
    def test_local_netcdf_preserves_valid_times_for_both_casts(self):
        for cast in ("nowcast", "forecast"):
            payload = fixture(cast)
            ds, url, cycle, failures, receipt = access.open_latest_station(
                cast, [CYCLE], Dataset, num2date, downloader=lambda _: payload)
            try:
                self.assertEqual(cycle, CYCLE)
                self.assertEqual(failures, [])
                self.assertIn(f"stations.{cast}.nc", url)
                self.assertEqual(receipt["bytes"], len(payload))
                self.assertEqual(receipt["embedded_time_validation"], "PASS")
                self.assertEqual(len(receipt["full_file_sha256"]), 64)
            finally:
                ds.close()

    def test_same_cycle_secondary_precedes_older_cycle(self):
        urls = access.station_http_urls(CYCLE, "nowcast")
        getter = Mock(side_effect=[HTTPError(urls[0], 503, "unavailable", {}, None), fixture()])
        ds, url, cycle, attempts, receipt = access.open_latest_station(
            "nowcast", [CYCLE, CYCLE-timedelta(hours=6)], Dataset, num2date, getter)
        ds.close()
        self.assertEqual(url, urls[1])
        self.assertEqual(cycle, CYCLE)
        self.assertEqual([x.args[0] for x in getter.call_args_list], list(urls))
        self.assertEqual(attempts[0]["http_status"], 503)

    def test_wrong_cast_cycle_and_partial_series_fail_without_retry(self):
        for payload in (fixture("forecast"), fixture(shift=360), fixture(missing_last=True)):
            getter = Mock(return_value=payload)
            with self.assertRaisesRegex(ValueError, "embedded valid times"):
                access.open_latest_station("nowcast", [CYCLE], Dataset, num2date, getter)
            self.assertEqual(getter.call_count, 1)

    def test_corrupt_netcdf_is_fatal_without_older_cycle_fallback(self):
        getter = Mock(return_value=b"not a dataset")
        with self.assertRaises(OSError):
            access.open_latest_station("nowcast", [CYCLE], Dataset, num2date, getter)
        self.assertEqual(getter.call_count, 1)

    def test_all_network_failures_preserve_structured_attempts(self):
        getter = Mock(side_effect=URLError("connection reset"))
        with self.assertRaises(access.StationRetrievalError) as caught:
            access.open_latest_station("nowcast", [CYCLE, CYCLE-timedelta(hours=6)], Dataset, num2date, getter)
        attempts = caught.exception.attempts
        self.assertEqual(len(attempts), 4)
        self.assertTrue(availability.retrieval_outage({"error_type": "StationRetrievalError", "retrieval_attempts": attempts}))
        attempts.append({"stage": "decode", "error_type": "ValueError", "error": "wrong cycle"})
        self.assertFalse(availability.retrieval_outage({"error_type": "StationRetrievalError", "retrieval_attempts": attempts}))

    def test_auth_and_bad_request_are_not_hidden_as_outages(self):
        for code in (400, 401, 403):
            getter = Mock(side_effect=HTTPError("https://noaa.gov", code, "error", {}, None))
            with self.assertRaises(HTTPError):
                access.open_latest_station("nowcast", [CYCLE], Dataset, num2date, getter)
            self.assertEqual(getter.call_count, 1)

    def test_full_payload_and_http_length_match(self):
        data = fixture()
        self.assertEqual(access.download("https://noaa.gov", lambda *a, **k: Response(data, len(data))), data)

    def test_html_truncation_and_size_are_rejected(self):
        cases = [(b"<html>maintenance</html>", None), (fixture(), 999999), (b"", access.MAX_BYTES+1)]
        for data, length in cases:
            with self.assertRaises(ValueError):
                access.download("https://noaa.gov", lambda *a, **k: Response(data, length))
        with patch.object(access, "MAX_BYTES", 10), self.assertRaisesRegex(ValueError, "bounded size"):
            access.download("https://noaa.gov", lambda *a, **k: Response(b"x" * 11))

    def test_streaming_deadline_is_enforced(self):
        with patch.object(access.time, "monotonic", side_effect=[0, 91]):
            with self.assertRaises(TimeoutError):
                access.download("https://noaa.gov", lambda *a, **k: Response(fixture()))

    def test_empty_or_unstructured_failure_set_is_not_an_outage(self):
        for attempts in (None, [], [{"error_type": "ValueError"}], [{"stage": "http_download", "error_type": "HTTPError", "http_status": 403}]):
            self.assertFalse(availability.retrieval_outage({"error_type": "StationRetrievalError", "retrieval_attempts": attempts}))

    def test_transport_failure_clears_old_csv_without_promoting_unknown(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, files in availability.PRODUCTS.items():
                (root / f"{name}_manifest.json").write_text(json.dumps({"status": "complete"}))
                for file in files:
                    (root / file).write_text("stale rows")
            target = "ngofs2_point_clear_nowcast"
            manifest = {"status": "failed", "error_type": "StationRetrievalError", "retrieval_attempts": [
                {"stage": "http_download", "error_type": "URLError", "error": "connection reset"}]}
            (root / f"{target}_manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(availability.validate(root)[target], "unavailable")
            self.assertFalse((root / f"{target}_normalized.csv").exists())
            saved = json.loads((root / f"{target}_manifest.json").read_text())
            self.assertEqual(saved["production_action"], "NO_CURRENT_GUIDANCE")
            self.assertEqual(saved["availability_reason"], "station_http_retrieval_unavailable_cause_unresolved")
            self.assertEqual(saved["retrieval_attempts"], manifest["retrieval_attempts"])

    def test_named_collector_retains_download_failure_evidence(self):
        import json
        from model_data import ingest_ngofs2_mobile_bay_named_stations as named
        attempts = [{"stage": "http_download", "error_type": "TimeoutError", "error": "timeout"}]
        with tempfile.TemporaryDirectory() as temp, patch.object(named, "HERE", Path(temp)), \
                patch.object(named, "open_latest", side_effect=access.StationRetrievalError(attempts)), \
                patch("sys.argv", ["collector", "--cast", "forecast"]):
            with self.assertRaises(SystemExit):
                named.main()
            saved = json.loads((Path(temp) / "ngofs2_mobile_bay_named_stations_forecast_manifest.json").read_text())
            self.assertEqual(saved["retrieval_attempts"], attempts)
            self.assertTrue(availability.retrieval_outage(saved))

    def test_noaa_urls_keep_exact_cycle_cast_and_current_directory_layout(self):
        urls = access.station_http_urls(CYCLE, "forecast")
        self.assertEqual(urls[0], "https://noaa-nos-ofs-pds.s3.amazonaws.com/ngofs2/netcdf/2026/10/14/ngofs2.t15z.20261014.stations.forecast.nc")
        self.assertIn("/fileServer/NOAA/NGOFS2/MODELS/2026/10/14/", urls[1])
        with self.assertRaises(ValueError):
            access.station_http_urls(CYCLE, "grid")

class HistoricalClockRegressionTests(unittest.TestCase):
    def clock_payload(self, name):
        import json
        record = json.loads((Path(__file__).parent / 'fixtures/ngofs2_forecast_clocks_20261022_24.json').read_text())[name]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'clock.nc'
            with Dataset(path, 'w') as ds:
                ds.title = record['title']
                ds.createDimension('time', len(record['raw_time_values']))
                t = ds.createVariable('time', 'f8', ('time',))
                t.units = record['units']
                t[:] = record['raw_time_values']
            return path.read_bytes()

    def failure(self):
        import hashlib
        payload = self.clock_payload('s3')
        cycle = datetime(2026, 10, 22, 3, tzinfo=timezone.utc)
        getter = Mock(return_value=payload)
        with self.assertRaises(access.StationTimeValidationError) as caught:
            access.open_latest_station('forecast', [cycle, cycle-timedelta(hours=6)], Dataset, num2date, getter)
        self.assertEqual(getter.call_count, 1)
        evidence = caught.exception.validation_failure
        self.assertEqual(evidence['full_file_sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(evidence['actual_count'], 481)
        self.assertEqual(evidence['paired_mismatch_count'], 3)
        self.assertEqual([m['index'] for m in evidence['mismatches']], [323, 328, 333])
        self.assertEqual([m['offset_seconds'] for m in evidence['mismatches']], [-1.0]*3)
        return caught.exception

    def test_recovered_oct22_clock_fails_with_exact_evidence_without_retry(self):
        self.failure()

    def test_oct24_replacement_clock_passes_unchanged_contract(self):
        cycle = datetime(2026, 10, 24, 9, tzinfo=timezone.utc)
        ds, _, _, _, receipt = access.open_latest_station(
            'forecast', [cycle], Dataset, num2date, lambda _: self.clock_payload('replacement'))
        ds.close()
        self.assertEqual(receipt['embedded_time_validation'], 'PASS')

    def test_both_collectors_persist_failure_and_availability_still_rejects(self):
        import json
        from model_data import ingest_ngofs2_point_clear as point
        from model_data import ingest_ngofs2_mobile_bay_named_stations as named
        error = self.failure()
        for collector, prefix in [(point, 'ngofs2_point_clear'), (named, 'ngofs2_mobile_bay_named_stations')]:
            with self.subTest(collector=prefix), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with patch.object(collector, 'HERE', root), patch.object(collector, 'open_latest', side_effect=error), \
                        patch('sys.argv', ['collector', '--cast', 'forecast']), patch('builtins.print'):
                    with self.assertRaises(SystemExit):
                        collector.main()
                manifest = json.loads((root / (prefix+'_forecast_manifest.json')).read_text())
                self.assertEqual(manifest['status'], 'failed')
                self.assertEqual(manifest['validation_failure'], error.validation_failure)
                self.assertFalse(availability.retrieval_outage(manifest))
                for name in availability.PRODUCTS:
                    p = root / (name+'_manifest.json')
                    if not p.exists():
                        p.write_text(json.dumps({'status':'complete'}))
                with self.assertRaisesRegex(RuntimeError, 'validation or parser failure'):
                    availability.validate(root)

    def test_mismatch_diagnostics_are_bounded(self):
        with self.assertRaises(access.StationTimeValidationError) as caught:
            access.open_latest_station('forecast', [CYCLE], Dataset, num2date,
                                       lambda _: fixture('forecast', shift=1))
        evidence = caught.exception.validation_failure
        self.assertEqual(evidence['paired_mismatch_count'], 481)
        self.assertEqual(len(evidence['mismatches']), 10)
        self.assertTrue(evidence['mismatches_truncated'])

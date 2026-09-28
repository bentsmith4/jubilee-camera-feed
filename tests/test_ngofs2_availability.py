import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "model_data" / "validate_ngofs2_availability.py"
spec = importlib.util.spec_from_file_location("ngofs2_availability", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runner_path = Path(__file__).resolve().parents[1] / "model_data" / "run_ngofs2_bounded.py"
runner_spec = importlib.util.spec_from_file_location("ngofs2_bounded", runner_path)
bounded = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(bounded)

# Failure fields from Actions run 36374092683 (2026-09-28 03:34:51Z).
DAP_FAILURE = {
    "schema_version": "1.2", "retrieved_at": "2026-09-28T03:33:05.642297+00:00",
    "cast": "nowcast", "status": "failed", "evidence_class": "MODEL",
    "production_action": "NO_CHANGE", "error_type": "RuntimeError",
    "error": "NetCDF: DAP server error",
}
DAP_URL = ("https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/NOAA/NGOFS2/MODELS/"
           "2026/09/27/ngofs2.t21z.20260927.stations.nowcast.nc")


class AvailabilityTests(unittest.TestCase):
    def make_root(self, root):
        for name, csvs in module.PRODUCTS.items():
            (root / f"{name}_manifest.json").write_text(json.dumps({"status": "complete"}))
            for csv in csvs:
                (root / csv).write_text("old model rows")

    def test_retrieval_failure_clears_stale_rows_and_marks_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_root(root)
            name = "ngofs2_point_clear_nowcast"
            (root / f"{name}_manifest.json").write_text(json.dumps({
                "status": "failed", "error_type": "RuntimeError",
                "error": "Unable to open any recent NGOFS2 station dataset: HTTP 503 Service Unavailable"
            }))
            result = module.validate(root)
            self.assertEqual(result[name], "unavailable")
            self.assertFalse((root / f"{name}_normalized.csv").exists())
            self.assertEqual(json.loads((root / f"{name}_manifest.json").read_text())["production_action"],
                             "NO_CURRENT_GUIDANCE")
            self.assertTrue((root / "ngofs2_point_clear_forecast_normalized.csv").exists())

    def test_parser_failure_stays_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_root(root)
            name = "ngofs2_point_clear_nowcast"
            (root / f"{name}_manifest.json").write_text(json.dumps({
                "status": "failed", "error_type": "ValueError", "error": "Missing NGOFS2 variables: ['u']"
            }))
            with self.assertRaises(RuntimeError):
                module.validate(root)

    def test_confirmed_netcdf_server_error_forms_are_retrieval_outages(self):
        for exc in (RuntimeError(DAP_FAILURE["error"]), OSError(-70, DAP_FAILURE["error"]),
                    OSError(-70, DAP_FAILURE["error"], DAP_URL)):
            with self.subTest(error=str(exc)):
                self.assertTrue(module.retrieval_outage({
                    "error_type": type(exc).__name__, "error": str(exc)}))

    def test_dap_outage_clears_only_affected_product_and_preserves_evidence(self):
        for name, csvs in module.PRODUCTS.items():
            with self.subTest(product=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_root(root)
                path = root / f"{name}_manifest.json"
                path.write_text(json.dumps(DAP_FAILURE))
                archive = root / "public_archive" / "previous.json.gz"
                archive.parent.mkdir()
                archive.write_bytes(b"immutable historical evidence")
                before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

                result = module.validate(root)

                self.assertEqual(result, {product: "unavailable" if product == name else "complete"
                                          for product in module.PRODUCTS})
                self.assertEqual(json.loads((root / "ngofs2_availability.json").read_text()), result)
                expected = {**DAP_FAILURE, "status": "unavailable",
                            "production_action": "NO_CURRENT_GUIDANCE",
                            "availability_reason": "upstream_retrieval_failure"}
                self.assertEqual(json.loads(path.read_text()), expected)
                for csv in csvs:
                    self.assertFalse((root / csv).exists())
                for other, content in before.items():
                    if other != path and other.name not in csvs:
                        self.assertEqual(other.read_bytes(), content)
                alias = root / "ngofs2_point_clear_manifest.json"
                if name == "ngofs2_point_clear_nowcast":
                    self.assertEqual(json.loads(alias.read_text()), expected)
                else:
                    self.assertFalse(alias.exists())

    def test_netcdf_and_ingestion_defects_stay_fatal(self):
        failures = [
            ("RuntimeError", "unrelated runtime failure"),
            ("ValueError", "NGOFS2 station dataset missing variables: ['u']"),
            ("KeyError", "time"),
            ("ValueError", "Could not uniquely resolve station 'Point Clear'; matches=[1, 2]"),
            ("ValueError", "Nearest NGOFS2 station is 20 km from Point Clear; refusing ambiguous mapping"),
            ("ValueError", "NGOFS2 extraction returned no rows"),
            ("ValueError", "No sigma layers"),
            ("RuntimeError", "NetCDF: DAP failure"),
            ("RuntimeError", "NetCDF: libcurl failure"),
            ("OSError", "NetCDF: I/O failure"),
            ("RuntimeError", "NetCDF: Variable has no data"),
            ("RuntimeError", "NetCDF: Malformed or inaccessible DAP DAS"),
            ("RuntimeError", "NetCDF: Malformed or inaccessible DAP2 DDS or DAP4 DMR response"),
            ("RuntimeError", "NetCDF: Malformed or inaccessible DAP2 DATADDS or DAP4 DAP response"),
            ("RuntimeError", "NetCDF: Malformed URL"),
            ("RuntimeError", "NetCDF: Malformed or unexpected Constraint"),
            ("OSError", "NetCDF: Authorization failure"),
            ("RuntimeError", "NetCDF: HDF error"),
            ("OSError", "NetCDF: Unknown file format"),
            # An embedded signature or a conflicting exception/code is not confirmation.
            ("ValueError", DAP_FAILURE["error"]),
            ("KeyError", DAP_FAILURE["error"]),
            ("RuntimeError", "Parser failed after NetCDF: DAP server error"),
            ("RuntimeError", "NetCDF: DAP server error; invalid schema"),
            ("OSError", "[Errno -72] NetCDF: DAP server error"),
            ("OSError", "[Errno -70] NetCDF: DAP server error: 'local.nc'"),
            ("RuntimeError", "Unable to open any recent NGOFS2 station dataset: "
                             "[{'error_type': 'RuntimeError', 'error': 'NetCDF: DAP server error'}, "
                             "{'error_type': 'ValueError', 'error': 'invalid schema'}]"),
        ]
        for error_type, error in failures:
            with self.subTest(error_type=error_type, error=error), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.make_root(root)
                path = root / "ngofs2_point_clear_nowcast_manifest.json"
                path.write_text(json.dumps({"status": "failed", "error_type": error_type, "error": error}))
                before = {p: p.read_bytes() for p in root.iterdir()}
                self.assertFalse(module.retrieval_outage({"error_type": error_type, "error": error}))
                with self.assertRaisesRegex(RuntimeError, "validation or parser failure"):
                    module.validate(root)
                self.assertEqual({p: p.read_bytes() for p in root.iterdir()}, before)

    def test_bounded_timeout_becomes_explicit_unavailable(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_root(root)
            def timeout(*args, **kwargs):
                raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
            self.assertEqual(bounded.run("named_stations_forecast", root, timeout), 1)
            result = module.validate(root)
            self.assertEqual(result["ngofs2_mobile_bay_named_stations_forecast"], "unavailable")
            self.assertFalse((root / "ngofs2_mobile_bay_named_stations_forecast_normalized.csv").exists())

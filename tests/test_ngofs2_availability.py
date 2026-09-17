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

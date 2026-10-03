import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "model_data/nearshore_current_20261002"
spec = importlib.util.spec_from_file_location("nearshore_coverage", HERE / "audit_coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class NearshoreCoverageTest(unittest.TestCase):
    def test_geometry_is_not_current_acceptance(self):
        result = coverage.audit()
        self.assertEqual(result, json.loads((HERE / "coverage_result.json").read_text()))
        self.assertEqual(result["accepted_earth_frame_rows"], 0)
        self.assertFalse(result["absence_of_all_datasets_proven"])
        self.assertTrue(all(r["scientific_acceptance"] == "NOT_PERFORMED_NO_VELOCITY_PAYLOAD" for r in result["candidates"]))

    def test_missing_and_invalid_geometry(self):
        ref = {"lat": 30.48664, "lon": -87.93453}
        self.assertIsNone(coverage.distance_km(None, -88, ref))
        with self.assertRaises(ValueError):
            coverage.distance_km(91, -88, ref)
        self.assertEqual(coverage.distance_km(ref["lat"], ref["lon"], ref), 0)

    def test_distance_and_lost_instrument_boundary(self):
        rows = {r["id"]: r for r in coverage.audit()["candidates"]}
        self.assertGreater(rows["DISL_MBLA"]["point_clear_distance_km"], 7.94)
        self.assertGreater(rows["mb0402"]["point_clear_distance_km"], 20)
        self.assertEqual(rows["MOB1103_LOST"]["disposition"], "LOST_NO_RECOVERED_DATA")
        self.assertFalse(rows["MOB1103_LOST"]["materially_closer_geometry_screen"])


if __name__ == "__main__":
    unittest.main()

"""Synthetic research QC tests. No historical NOAA rows are asserted ingested."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "model_data" / "validate_middle_bay_2019_candidate.py"
spec = importlib.util.spec_from_file_location("middle_bay_qc", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def candidate(**updates):
    item = {
        "accession": "0224293",
        "stationid": "188",
        "kind": "hydro",
        "native_schema_verified": True,
        "source_time_basis_verified": True,
        "sensor_deployment_verified": True,
        "observed_at": "2019-06-02T05:00:00-05:00",
        "available_at": "2019-06-02T06:00:00-05:00",
        "parameter": "dissolved_oxygen_mg_l",
        "units": "mg/L",
        "native_qc": 3,
        "value": 6.5,
        "sensor_height_above_bed_m": 1.0,
        "depth_datum": "explicit-deployment-reference",
        "raw_sha256": "49e04d4903d6f6edc4f6bbbc91e9b7e81a6c6ed560318a0621d1d9c454c5e7fb",
        "raw_file_id": "synthetic_fixture_not_real_NCEI_file",
    }
    item.update(updates)
    return item


class MiddleBayQcTests(unittest.TestCase):
    def test_good_schema_only_eligible_with_asof(self):
        r = mod.evaluate_candidate(candidate(), "2019-06-02T06:30:00-05:00")
        self.assertTrue(r["scientific_qc_admissible"])
        self.assertTrue(r["forecast_time_eligible"])
        self.assertEqual(r["production_weight"], 0)
        self.assertFalse(r["point_clear_bottom_state_eligible"])

    def test_after_hydro_outage_is_not_valid(self):
        r = mod.evaluate_candidate(candidate(observed_at="2019-07-04T00:00:00-05:00"))
        self.assertIn("outside_verified_hydro_period", r["reasons"])

    def test_mislabeled_percent_not_mg_l(self):
        r = mod.evaluate_candidate(candidate(units="%"))
        self.assertIn("units_unverified", r["reasons"])

    def test_water_height_not_accepted(self):
        r = mod.evaluate_candidate(candidate(parameter="water_height", units="m"))
        self.assertIn("unapproved_or_unknown_parameter", r["reasons"])

    def test_suspect_not_good(self):
        r = mod.evaluate_candidate(candidate(native_qc=2))
        self.assertIn("not_native_qc_good", r["reasons"])

    def test_unknown_depth_not_silently_accepted(self):
        r = mod.evaluate_candidate(candidate(sensor_height_above_bed_m=None))
        self.assertIn("sensor_height_not_verified", r["reasons"])

    def test_native_schema_gate(self):
        r = mod.evaluate_candidate(candidate(native_schema_verified=False))
        self.assertIn("native_schema_not_verified", r["reasons"])

    def test_unverified_time_basis_gate(self):
        r = mod.evaluate_candidate(candidate(source_time_basis_verified=False))
        self.assertIn("source_time_basis_not_verified", r["reasons"])

    def test_unverified_deployment_gate(self):
        r = mod.evaluate_candidate(candidate(sensor_deployment_verified=False))
        self.assertIn("sensor_deployment_not_verified", r["reasons"])

    def test_temporal_leakage_fails_forecast_time_not_scientific_qc(self):
        r = mod.evaluate_candidate(candidate(available_at="2026-10-20T00:00:00Z"), "2019-06-02T06:30:00-05:00")
        self.assertTrue(r["scientific_qc_admissible"])
        self.assertFalse(r["forecast_time_eligible"])
        self.assertIn("not_available_as_of_issue", r["reasons"])

    def test_naive_local_clock_fails(self):
        r = mod.evaluate_candidate(candidate(observed_at="2019-06-02T05:00:00"))
        self.assertIn("observation_timezone_unknown", r["reasons"])

    def test_different_sha_fails(self):
        r = mod.evaluate_candidate(candidate(raw_sha256="a" * 64))
        self.assertIn("wrong_original_source_hash", r["reasons"])

    def test_wrong_station_fails(self):
        r = mod.evaluate_candidate(candidate(stationid="999"))
        self.assertIn("wrong_station_or_missing_station", r["reasons"])

    def test_missing_hash_fails(self):
        r = mod.evaluate_candidate(candidate(raw_sha256=""))
        self.assertIn("raw_hash_absent", r["reasons"])

    def test_rejected_parameter_cannot_be_earth_current(self):
        r = mod.evaluate_candidate(candidate(parameter="eastward_current_m_s", units="m/s"))
        self.assertFalse(r["earth_frame_current_eligible"])
        self.assertFalse(r["scientific_qc_admissible"])


if __name__ == "__main__":
    unittest.main()

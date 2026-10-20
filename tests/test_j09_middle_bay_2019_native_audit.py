"""Native NOAA source audit: synthetic structure, no purchased data or model calls."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "model_data" / "audit_middle_bay_2019_native.py"
spec = importlib.util.spec_from_file_location("j09_native_middle_bay", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
HEADER = ("yeardata,jday,timedata,stationid,Dissoved Oxygen mgl,"
          "Dissoved Oxygen mgl flag,Dissoved Oxygen percent,"
          "Dissoved Oxygen Percent flag,Water Temperature,Water Temperature Flag,"
          "Salinity,Salinity Flag,Pressure,Water Height,Water Height Flag")
BASE = "2019,1,30,188,1.5,3,20.0,3,18.0,3,8.0,3,2.0,1.0,3"


def raw(body=BASE):
    return (HEADER + "\n" + body + "\n").encode("utf-8")


class NativeMiddleBayTests(unittest.TestCase):
    def test_original_hash_mandatory(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            mod.audit_bytes(raw())

    def test_fixture_parses_only_when_original_gate_disabled(self):
        audit = mod.audit_bytes(raw(), require_original=False)
        self.assertEqual(audit["rows"], 1)
        self.assertEqual(audit["measure_ranges"]["do_mg_l"]["below_2"], 1)
        self.assertEqual(audit["clock_timezone"], "UNKNOWN_NOT_NORMALIZED")
        self.assertEqual(audit["forecast_production_weight"], 0)

    def test_native_2400_is_not_assigned_utc(self):
        a = mod.audit_bytes(raw(BASE.replace(",30,188,", ",2400,188,")), require_original=False)
        self.assertEqual(a["nominal_month_counts"], {"2019-01": 1})

    def test_invalid_source_year_rejected(self):
        with self.assertRaisesRegex(ValueError, "unparseable"):
            mod.audit_bytes(raw(BASE.replace("2019,1", "2020,1")), require_original=False)

    def test_duplicate_native_time_key_counted(self):
        a = mod.audit_bytes(raw(BASE + "\n" + BASE), require_original=False)
        self.assertEqual(a["duplicate_native_keys"], 1)

    def test_column_width_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "column-width"):
            mod.audit_bytes(raw(BASE + ",unexpected"), require_original=False)

    def test_unverified_water_height_not_usable(self):
        a = mod.audit_bytes(raw(), require_original=False)
        self.assertEqual(a["water_height_units"], "UNRESOLVED_NOT_USED")
        self.assertEqual(a["point_clear_current_rows"], 0)


if __name__ == "__main__":
    unittest.main()

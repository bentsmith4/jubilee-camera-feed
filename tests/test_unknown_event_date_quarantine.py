import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model_data"))

import backtest_water_quality as wqp
from evaluate_lunar_phase import load_events


class UnknownEventDateQuarantineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = json.loads((ROOT / "model_data" / "event_history.json").read_text())
        cls.row = next(
            event for event in cls.history["events"]
            if event["event_id"] == "2024-08-05-mobile-bay-eastern-shore"
        )

    def test_stjohn_identity_is_preserved_but_date_is_unknown(self):
        self.assertIsNone(self.row["event_date_ct"])
        self.assertEqual(self.row["date_precision"], "unknown")
        self.assertIn("scoring denominators", self.row["quarantined_from"])
        self.assertNotIn("date", self.row["evidence"][0]["supports"])

    def test_water_quality_denominator_excludes_unknown_date(self):
        report = wqp.analyze([], self.history)
        self.assertEqual(report["confirmed_events_in_database"], 18)
        self.assertEqual(report["confirmed_event_rows_without_valid_date"], 1)
        self.assertEqual(
            report["confirmed_event_ids_without_valid_date"],
            ["2024-08-05-mobile-bay-eastern-shore"],
        )

    def test_lunar_diagnostic_excludes_unknown_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event_history.json"
            path.write_text(json.dumps(self.history), encoding="utf-8")
            rows = load_events(path, "1959-07-07")
        ids = {row["event_id"] for row in rows}
        self.assertEqual(len(rows), 18)
        self.assertNotIn("2024-08-05-mobile-bay-eastern-shore", ids)


if __name__ == "__main__":
    unittest.main()

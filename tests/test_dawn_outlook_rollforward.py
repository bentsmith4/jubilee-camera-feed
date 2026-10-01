"""Offline tests for reviewed zero-change Jubilee Dawn horizon maintenance."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model_data"))
sys.path.insert(0, str(ROOT / "tests"))

import bind_current_forecast as binding
import test_current_forecast as fixture

spec = importlib.util.spec_from_file_location("roll_forward_dawn_outlook", ROOT / "model_data/roll_forward_dawn_outlook.py")
roll = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roll)


class DawnOutlookRollForwardTests(unittest.TestCase):
    def setUp(self):
        self.state = fixture.snapshot()
        self.state["snapshot_time_ct"] = "2026-10-01T06:45:00-05:00"
        self.state["reconciliation"]["as_of_utc"] = "2026-10-01T11:45:00+00:00"
        template = copy.deepcopy(self.state["outlook"][0])
        self.state["outlook"] = []
        for date_ct in ("2026-09-28", "2026-09-29", "2026-09-30"):
            day = copy.deepcopy(template)
            day["date_ct"] = date_ct
            self.state["outlook"].append(day)
        self.raw = fixture.encode(self.state)
        self.forecast = binding.project(self.raw)

    def test_rolls_dates_only_and_preserves_policy(self):
        result = roll.build(self.raw, self.forecast, "2026-10-01T06:46:00-05:00")
        self.assertIsNotNone(result)
        snapshot_raw, forecast_raw = result
        snapshot, forecast = json.loads(snapshot_raw), json.loads(forecast_raw)
        self.assertEqual([x["date_ct"] for x in snapshot["outlook"]],
                         ["2026-10-01", "2026-10-02", "2026-10-03"])
        self.assertEqual([roll.profile(x) for x in snapshot["outlook"]],
                         [roll.profile(x) for x in self.state["outlook"]])
        self.assertEqual(snapshot["alert_gates"], self.state["alert_gates"])
        self.assertEqual(forecast["alert_gates"], self.forecast["alert_gates"])
        self.assertFalse(forecast["forecast_weights_changed"])
        binding.check(snapshot_raw, forecast)
        binding.require_dawn_horizon(snapshot)

    def test_different_daily_profiles_require_explicit_reassessment(self):
        self.state["outlook"][1]["point_clear_central_percent"] += 1
        raw = fixture.encode(self.state)
        forecast = binding.project(raw)
        with self.assertRaisesRegex(ValueError, "REVIEW_REQUIRED: daily heuristic profiles differ"):
            roll.build(raw, forecast, "2026-10-01T06:46:00-05:00")

    def test_stale_issue_date_or_out_of_season_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "current-date snapshot"):
            roll.build(self.raw, self.forecast, "2026-10-02T06:46:00-05:00")

        state = copy.deepcopy(self.state)
        state["snapshot_time_ct"] = "2026-12-01T06:45:00-06:00"
        state["reconciliation"]["as_of_utc"] = "2026-12-01T12:45:00+00:00"
        raw = fixture.encode(state)
        forecast = binding.project(raw)
        with self.assertRaisesRegex(ValueError, "outside May 18-November 14"):
            roll.build(raw, forecast, "2026-12-01T06:46:00-06:00")

    def test_already_current_horizon_is_idempotent(self):
        first = roll.build(self.raw, self.forecast, "2026-10-01T06:46:00-05:00")
        snapshot_raw, forecast_raw = first
        self.assertIsNone(roll.build(snapshot_raw, json.loads(forecast_raw), "2026-10-01T06:47:00-05:00"))


if __name__ == "__main__":
    unittest.main()

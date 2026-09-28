import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))
sys.modules["refresh_all"] = types.SimpleNamespace()

from capture_service import (
    pending_capture,
    slot,
    spacing_ready,
    strong_activity_evidence,
)


class Schedule(unittest.TestCase):
    def test_hour_boundary(self):
        start = datetime(2026, 9, 6, 4, 6, 25, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        now = start.replace(hour=17, minute=5, second=59)
        self.assertIn("16:06:00", slot(now, start, end))
        self.assertIn("17:06:00", slot(now + timedelta(seconds=1), start, end))

    def test_twenty_minute_dawn_slots(self):
        start = datetime(2026, 9, 6, 4, 6, 25, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        self.assertEqual(slot(start, start, end), "dawn:2026-09-06:0")
        self.assertEqual(
            slot(start + timedelta(minutes=19), start, end),
            "dawn:2026-09-06:0",
        )
        self.assertEqual(
            slot(start + timedelta(minutes=20), start, end),
            "dawn:2026-09-06:1",
        )
        self.assertEqual(slot(end, start, end), "dawn:2026-09-06:12")

    def test_overnight_baseline_is_roughly_halved(self):
        start = datetime(2026, 9, 6, 4, 19, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        expected = {
            20: True,
            21: False,
            22: True,
            23: False,
            0: True,
            1: False,
            2: True,
            3: False,
            4: True,
        }
        for hour, enabled in expected.items():
            with self.subTest(hour=hour):
                day = 5 if hour >= 20 else 6
                now = datetime(2026, 9, day, hour, 6, tzinfo=timezone.utc)
                result = slot(now, start, end)
                self.assertEqual(result is not None, enabled)

    def test_global_spacing_blocks_hour_to_dawn_handoff_under_15_minutes(self):
        now = datetime(2026, 9, 28, 4, 19, tzinfo=timezone.utc)
        state = {"last_canonical_success": "2026-09-28T04:06:00+00:00"}
        self.assertFalse(spacing_ready(now, state))
        self.assertTrue(spacing_ready(now + timedelta(minutes=2), state))

    def test_regular_dawn_slot_waits_for_spacing_floor(self):
        start = datetime(2026, 9, 28, 4, 19, tzinfo=timezone.utc)
        dawn = start + timedelta(hours=2)
        end = dawn + timedelta(hours=2)
        state = {
            "last_regular_slot": "hour:2026-09-28T04:06:00+00:00",
            "last_canonical_success": "2026-09-28T04:06:00+00:00",
        }
        due = pending_capture(start, dawn, start, end, state, activity=False)
        self.assertEqual(due, "dawn:2026-09-28:0")
        self.assertFalse(spacing_ready(start, state))
        self.assertTrue(spacing_ready(start + timedelta(minutes=2), state))

    def test_strong_fresh_activity_can_accelerate_pre_dawn_to_floor(self):
        start = datetime(2026, 9, 28, 4, 19, tzinfo=timezone.utc)
        dawn = start + timedelta(hours=2)
        end = dawn + timedelta(hours=2)
        last = start + timedelta(minutes=1)
        now = last + timedelta(minutes=15)
        state = {
            "last_regular_slot": "dawn:2026-09-28:0",
            "canonical_slot": "dawn:2026-09-28:0",
            "last_canonical_success": last.isoformat(),
        }
        vision = {
            "capture_time_ct": last.isoformat(),
            "cross_camera": {"overall_visual_jubilee_signal": "none"},
            "cameras": {
                "montrose_shoreline": {
                    "status": "ok",
                    "flashlight_activity": "clear",
                    "clustered_search_behavior": "clear",
                    "people_collecting_seafood": "none_visible",
                    "motion_pattern": "searching",
                    "human_sensor_score": 0.8,
                    "human_sensor_detectability": "good",
                    "temporal_jubilee_signal": "none",
                    "overall_jubilee_visual_signal": "none",
                }
            },
        }
        self.assertTrue(strong_activity_evidence(vision, now))
        due = pending_capture(now, dawn, start, end, state, activity=True)
        self.assertTrue(due.startswith("adaptive:"))
        self.assertTrue(spacing_ready(now, state))

    def test_weak_or_stale_activity_does_not_accelerate(self):
        now = datetime(2026, 9, 28, 5, 0, tzinfo=timezone.utc)
        weak = {
            "capture_time_ct": (now - timedelta(minutes=10)).isoformat(),
            "cross_camera": {"overall_visual_jubilee_signal": "weak_possible"},
            "cameras": {
                "montrose_shoreline": {
                    "status": "ok",
                    "flashlight_activity": "possible",
                    "clustered_search_behavior": "possible",
                    "people_collecting_seafood": "possible",
                    "motion_pattern": "searching",
                    "human_sensor_score": 0.25,
                    "human_sensor_detectability": "good",
                    "temporal_jubilee_signal": "weak_possible",
                    "overall_jubilee_visual_signal": "weak_possible",
                }
            },
        }
        self.assertFalse(strong_activity_evidence(weak, now))
        weak["capture_time_ct"] = (now - timedelta(minutes=61)).isoformat()
        weak["cross_camera"]["overall_visual_jubilee_signal"] = "strong"
        self.assertFalse(strong_activity_evidence(weak, now))


if __name__ == "__main__":
    unittest.main()

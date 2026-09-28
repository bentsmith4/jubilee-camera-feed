import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))

import types
import unittest
from datetime import datetime, timedelta, timezone

sys.modules["refresh_all"] = types.SimpleNamespace()

from capture_service import adaptive_active, slot, spacing_remaining, strong_activity_evidence


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
        self.assertEqual(slot(start + timedelta(minutes=19), start, end), "dawn:2026-09-06:0")
        self.assertEqual(slot(start + timedelta(minutes=20), start, end), "dawn:2026-09-06:1")
        self.assertEqual(slot(end, start, end), "dawn:2026-09-06:12")

    def test_overnight_baseline_is_reduced_roughly_in_half(self):
        start = datetime(2026, 9, 6, 6, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        for hour in (20, 22):
            self.assertTrue(slot(datetime(2026, 9, 6, hour, 6, tzinfo=timezone.utc), start, end).startswith("hour:"))
        for hour in (21, 23):
            self.assertIsNone(slot(datetime(2026, 9, 6, hour, 6, tzinfo=timezone.utc), start, end))

        next_start = datetime(2026, 9, 7, 6, 0, tzinfo=timezone.utc)
        next_end = next_start + timedelta(hours=4)
        for hour in (0, 2, 4):
            self.assertTrue(slot(datetime(2026, 9, 7, hour, 6, tzinfo=timezone.utc), next_start, next_end).startswith("hour:"))
        for hour in (1, 3):
            self.assertIsNone(slot(datetime(2026, 9, 7, hour, 6, tzinfo=timezone.utc), next_start, next_end))

    def test_hourly_to_dawn_handoff_suppresses_too_close_baseline(self):
        start = datetime(2026, 9, 28, 4, 19, tzinfo=timezone.utc)
        end = start + timedelta(hours=4)
        self.assertIsNone(slot(datetime(2026, 9, 28, 4, 6, tzinfo=timezone.utc), start, end))

    def test_global_spacing_blocks_thirteen_minute_handoff(self):
        last = datetime(2026, 9, 28, 4, 6, tzinfo=timezone.utc)
        self.assertEqual(
            spacing_remaining(datetime(2026, 9, 28, 4, 19, tzinfo=timezone.utc), last),
            timedelta(minutes=2),
        )
        self.assertEqual(
            spacing_remaining(datetime(2026, 9, 28, 4, 21, tzinfo=timezone.utc), last),
            timedelta(0),
        )

    def test_strong_predawn_activity_accelerates_to_fifteen_minutes(self):
        start = datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)
        dawn = start + timedelta(hours=2)
        end = start + timedelta(hours=4)
        vision = {
            "cameras": {
                "montrose_shoreline": {
                    "status": "ok",
                    "confidence": 0.9,
                    "human_sensor_detectability": "good",
                    "flashlight_activity": "clear",
                    "clustered_search_behavior": "clear",
                }
            }
        }
        at = start + timedelta(minutes=15)
        self.assertTrue(strong_activity_evidence(vision))
        self.assertTrue(adaptive_active(at, dawn, start, end, vision))
        self.assertEqual(slot(at, start, end, adaptive=True), "dawn-adaptive:2026-09-28:1")
        self.assertEqual(slot(at, start, end, adaptive=False), "dawn:2026-09-28:0")

    def test_weak_or_postdawn_evidence_does_not_accelerate(self):
        start = datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)
        dawn = start + timedelta(hours=2)
        end = start + timedelta(hours=4)
        weak = {
            "cameras": {
                "montrose_shoreline": {
                    "status": "ok",
                    "confidence": 0.9,
                    "human_sensor_detectability": "good",
                    "flashlight_activity": "possible",
                    "overall_jubilee_visual_signal": "weak_possible",
                }
            }
        }
        self.assertFalse(strong_activity_evidence(weak))
        self.assertFalse(adaptive_active(start + timedelta(minutes=15), dawn, start, end, weak))

        strong = {"cross_camera": {"overall_visual_jubilee_signal": "strong"}}
        self.assertFalse(adaptive_active(dawn + timedelta(minutes=1), dawn, start, end, strong))


if __name__ == "__main__":
    unittest.main()

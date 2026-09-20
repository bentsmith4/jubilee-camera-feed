import json
import tempfile
import unittest
from pathlib import Path

from model_data.evaluate_lunar_phase import evaluate, phase_fraction


class LunarPhaseEvaluationTests(unittest.TestCase):
    def test_reference_new_moon_phase_is_near_zero(self):
        # Representative 11:00Z is 7.24 hours before the epoch new moon.
        self.assertGreater(phase_fraction("2000-01-06"), 0.989)

    def test_episode_blocking_and_no_skill_claim(self):
        history = {
            "events": [
                {"event_id": "1971-08-07-point-clear-corridor", "event_date_ct": "1971-08-07", "classification": "confirmed_jubilee"},
                {"event_id": "1971-08-08-point-clear-corridor-major", "event_date_ct": "1971-08-08", "classification": "confirmed_jubilee"},
                {"event_id": "2026-08-29-fairhope-point-clear-multipocket", "event_date_ct": "2026-08-29", "classification": "confirmed_jubilee"},
                {"event_id": "2026-08-30-fairhope-north-of-pier-localized", "event_date_ct": "2026-08-30", "classification": "confirmed_jubilee"},
                {"event_id": "1959-07-point-clear-south-grand-hotel", "event_date_ct": "1959-07-07", "classification": "confirmed_jubilee"},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event_history.json"
            path.write_text(json.dumps(history), encoding="utf-8")
            result = evaluate(path)
        self.assertEqual(result["sample"]["confirmed_event_rows"], 5)
        self.assertEqual(result["sample"]["independent_event_episodes"], 3)
        self.assertEqual(result["sample"]["clean_matched_non_event_controls"], 0)
        self.assertEqual(result["decision"]["production_weight"], 0.0)
        self.assertEqual(result["decision"]["incremental_value"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()

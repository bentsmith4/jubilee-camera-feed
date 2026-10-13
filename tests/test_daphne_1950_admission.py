"""Pin the single J08 admission without rewriting earlier recovery audits."""
from datetime import date, timedelta
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "model_data"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Daphne1950AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.events = load("event_history.json")["events"]
        self.event = next(e for e in self.events if e["event_id"] == "1950-09-17-daphne")
        self.scan = load("loesch_newspaper_scan_evidence_20261003.json")

    def test_exactly_one_new_research_only_event(self):
        self.assertEqual(len(self.events), 16)
        self.assertEqual(len({e["event_id"] for e in self.events}), 16)
        period = [e["event_id"] for e in self.events
                  if "1946-01-01" <= e["event_date_ct"] <= "1956-12-31"]
        self.assertEqual(period, ["1950-09-17-daphne"])
        self.assertIs(self.event["research_only"], True)
        self.assertEqual(self.event["production_weight"], 0)
        self.assertEqual(self.event["classification"], "confirmed_jubilee")
        self.assertIn("not an empirically calibrated probability", self.event["confidence_qualification"])

    def test_publication_day_is_not_the_event_day(self):
        self.assertEqual(self.event["event_date_ct"], "1950-09-17")
        evidence = self.event["evidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["source_publication_date"], "1950-09-18")
        event_day = date.fromisoformat(self.event["event_date_ct"])
        self.assertEqual(event_day.weekday(), 6)  # Sunday
        self.assertEqual(event_day + timedelta(days=1), date(1950, 9, 18))
        self.assertEqual(self.event["date_precision"],
                         "day_inferred_from_contemporaneous_issue_date_relative_weekday_and_calendar")

    def test_one_newspaper_group_has_original_source_provenance(self):
        evidence = self.event["evidence"]
        self.assertEqual(len(evidence), 1)
        source = evidence[0]
        self.assertEqual(source["type"], "contemporaneous_newspaper_scan")
        self.assertEqual(source["independence_group"], "1950_09_17_mobile_press_daphne")
        self.assertEqual(source["source_sha256"],
                         "1087181cb1ea78aa7ccc33e49637f47d17c4d4fd9b5b3eaf69709a45bc978e6c")
        self.assertEqual(source["source_library_file_id"], "libfile_b4f200a92c94819192c074218b2aaae6")
        self.assertEqual(source["source_observation_id"], "1950-09-17-daphne-report")
        retained = next(s for s in self.scan["sources"] if s["publication_date"] == "1950-09-18")
        self.assertEqual(retained["sha256"], source["source_sha256"])
        self.assertEqual(retained["bytes"], 1387225)
        self.assertEqual(retained["library_file_id"], source["source_library_file_id"])
        observation = next(o for o in self.scan["observations"]
                           if o["id"] == source["source_observation_id"])
        self.assertEqual(observation["event_date"], self.event["event_date_ct"])
        self.assertEqual(observation["source"], source["source_publication_date"])
        self.assertEqual(observation["species"], self.event["reported_species"])
        self.assertEqual(self.event["reported_species"],
                         ["flounder", "hard-shell crab", "soft-shell crab", "eel"])

    def test_approximate_time_and_locality_are_not_overstated(self):
        self.assertEqual(self.event["reported_event_time_local"],
                         "about 5:30 p.m. Sunday until around midnight")
        self.assertEqual(self.event["time_precision"],
                         "approximate_reported_local_clock_bounds_not_verified_exact_onset_or_end")
        self.assertEqual(self.event["time_standard"], "UNKNOWN; no historical UTC offset asserted")
        self.assertIn("seven hours", self.event["reported_duration"])
        self.assertIn("about 6.5 hours", self.event["reported_duration"])
        self.assertIs(self.event["location"]["continuous_boundary_claimed"], False)
        self.assertIn("approximately one mile south of Daphne", self.event["location"]["label"])

    def test_photo_is_unlinked_and_battles_wharf_is_not_an_extra_event(self):
        notes = self.event["notes"]
        self.assertIn("S-249-16 / 35H-B3-12-3", notes)
        self.assertIn("same-event identity remain UNESTABLISHED", notes)
        self.assertIn("not counted as independent corroboration or another event", notes)
        same_day = [e["event_id"] for e in self.events if e["event_date_ct"] == "1950-09-17"]
        self.assertEqual(same_day, ["1950-09-17-daphne"])
        battles = next(o for o in self.scan["observations"]
                       if o["id"] == "1950-09-17-battles-wharf-report")
        self.assertIn("independence UNKNOWN", battles["separateness"])
        self.assertIs(battles["research_only"], True)
        self.assertEqual(battles["production_weight"], 0)
        # These are October 3 outcomes, not assertions about today's history.
        self.assertEqual(self.scan["model_use"]["canonical_events_added"], 0)
        self.assertIs(self.scan["model_use"]["production_changes"], False)
        self.assertEqual(self.scan["model_use"]["controls_created"], 0)


if __name__ == "__main__":
    unittest.main()

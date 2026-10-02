"""Guard historical count evidence against accidental event-row promotion."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "model_data"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class LoeschRecoveryTests(unittest.TestCase):
    def test_discrepant_counts_stay_aggregate_only(self):
        audit = load("loesch_1960_recovery_20260929.json")
        self.assertEqual({c["count"] for c in audit["count_claims"]}, {35, 37})
        self.assertEqual(sum(audit["count_claims"][1]["month_counts"].values()), 37)
        self.assertEqual(audit["count_reconciliation"]["difference"], 2)
        self.assertIsNone(audit["count_reconciliation"]["explanation"])
        self.assertIsNone(audit["count_reconciliation"]["production_count_selected"])
        self.assertFalse(audit["primary_source"]["event_table_recovered"])
        self.assertEqual(audit["new_event_rows"], [])
        self.assertTrue(audit["aggregate_only"])
        self.assertEqual(audit["production_action"], "NO_CHANGE")

    def test_canonical_history_does_not_invent_loesch_period_rows(self):
        audit = load("loesch_1960_recovery_20260929.json")
        events = load("event_history.json")["events"]
        self.assertEqual(len(events), audit["canonical_before_review"])
        self.assertEqual(len({e["event_id"] for e in events}), len(events))
        overlap = [e for e in events if "1946-01-01" <= e["event_date_ct"] <= "1956-12-31"]
        self.assertEqual(overlap, [])
        self.assertEqual(audit["canonical_event_ids_in_1946_1956"], [])

    def test_registry_retains_source_status_and_separate_claims(self):
        registry = load("historical_event_source_registry.json")
        source = next(s for s in registry["sources"] if s["source_id"] == "loesch_1960_ecology")
        self.assertEqual(source["status"], "primary_pages_recovered_internal_count_discrepancy_unresolved")
        self.assertEqual(source["count_reconciliation_status"], "unresolved_internal_primary_table_inconsistency")
        self.assertEqual({c["count"] for c in source["aggregate_count_claims"]}, {35, 37})
        self.assertNotIn("reported_event_count_secondary", source)


if __name__ == "__main__":
    unittest.main()

"""Research provenance and chronology boundaries after full primary recovery."""
import hashlib
from copy import deepcopy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'model_data'

def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

class LoeschPrimaryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.audit = load('loesch_1960_primary_recovery_20261002.json')

    def test_primary_arithmetic_retains_internal_discrepancy(self):
        c = self.audit['count_evidence']
        self.assertEqual(list(c['annual_counts']), list(map(str, range(1946, 1957))))
        self.assertEqual(sum(c['annual_counts'].values()), 35)
        self.assertEqual(sum(c['monthly_counts'].values()), 37)
        self.assertEqual(sum(c['shore_counts'].values()), 35)
        self.assertEqual(sum(c['table_II_day_before_counts'].values()), 33)
        self.assertEqual(sum(c['table_II_at_time_counts'].values()), 33)
        self.assertIsNone(c['explanation'])
        self.assertIsNone(c['production_count_selected'])
        self.assertFalse(c['same_night_two_location_reports']['can_explain_difference'])

    def test_all_seven_pages_have_unambiguous_provenance(self):
        pages = self.audit['page_provenance']
        self.assertEqual([p['printed_page'] for p in pages], list(range(292, 299)))
        self.assertEqual([p['pdf_page_1_based'] for p in pages], list(range(44, 51)))
        self.assertTrue(all(p['visual_review_completed'] for p in pages))
        self.assertTrue(self.audit['primary_source']['full_pages_recovered'])
        self.assertFalse(self.audit['primary_source']['full_individual_event_roster_present'])
        self.assertRegex(self.audit['primary_source']['issue_pdf_sha256'], r'^[a-f0-9]{64}$')

    def test_clipping_dates_cannot_become_exact_event_dates(self):
        rows = self.audit['research_records']
        clips = [r for r in rows if r['kind'] == 'dated_newspaper_excerpt']
        self.assertEqual({r['source_date'] for r in clips}, {'1947-06-16','1950-08-07','1950-09-18'})
        self.assertTrue(all(r['event_date'] is None and r['shoreline_cell'] is None for r in clips))
        positives = [r for r in rows if r['kind'] == 'explicit_dated_positive']
        self.assertEqual({r['event_date'] for r in positives}, {'1955-08-16','1957-07-12'})
        self.assertTrue(all(not r['sampling_locations_are_event_extent'] for r in positives))
        later = next(r for r in positives if r['event_date'] == '1957-07-12')
        self.assertTrue(later['outside_1946_1956_count_period'])
        self.assertTrue(all(not r['calibration_eligible'] for r in rows))

    def test_scoped_near_miss_is_not_a_positive_or_tier_a_control(self):
        row = next(r for r in self.audit['research_records'] if r['kind'] == 'scoped_non_event')
        self.assertEqual(row['event_date'], '1955-07-28')
        self.assertFalse(row['positive_event_report'])
        self.assertFalse(row['whole_morning_control'])
        self.assertIsNone(row['location'])

    def test_original_history_and_historical_deduplication_are_unchanged(self):
        history = load('event_history.json')
        current_events = history['events']
        self.assertEqual(len(current_events), 16)
        self.assertEqual(len({e['event_id'] for e in current_events}), 16)
        self.assertEqual(sum(e['event_id'] == '1950-09-17-daphne'
                             for e in current_events), 1)
        # Remove only the explicitly reviewed J08 addition. This reconstructs
        # the original serialized document, including metadata and event order;
        # a count-only check would miss edits to any of the original 15 rows.
        original = deepcopy(history)
        original['events'] = [e for e in original['events']
                              if e['event_id'] != '1950-09-17-daphne']
        events = original['events']
        self.assertEqual(len(events), 15)
        original_bytes = (json.dumps(original, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        original_sha = 'dab32ef7e5a0bf4edefb8e998a759ef30aa551feafe61da4d78bbb266cf4dca2'
        self.assertEqual(hashlib.sha256(original_bytes).hexdigest(), original_sha)
        review = self.audit['canonical_review']
        self.assertEqual(review['history_sha256'], original_sha)
        self.assertEqual(review['count_before'], 15)
        self.assertEqual(review['count_after'], 15)
        self.assertEqual(review['exact_date_matches'], [])
        self.assertEqual(review['period_1946_1956_existing_records'], [])
        for row in self.audit['research_records']:
            matches = [e['event_id'] for e in events if row.get('event_date') and e['event_date_ct'] == row['event_date']]
            self.assertEqual(matches, row['canonical_match_ids'])
        self.assertEqual(self.audit['canonical_review']['rows_promoted'], 0)
        self.assertEqual(self.audit['production_action'], 'NO_CHANGE')
        self.assertFalse(self.audit['archival_requests_sent'])

if __name__ == '__main__':
    unittest.main()

"""Evidence/contract regression for the fixed September 30 research review."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def git_blob(path):
    raw = (ROOT / path).read_bytes()
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


class MontroseControlReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = read('model_data/j10_montrose_control_verification_20260930.json')
        cls.contract = read('model_data/matched_control_contract.json')

    def test_contract_and_evidence_provenance(self):
        self.assertEqual(git_blob(self.review['contract']['path']), self.review['contract']['blob_sha'])
        for ep in self.review['episodes']:
            self.assertEqual(git_blob(ep['original_audit']['path']), ep['original_audit']['blob_sha'])
            for row in ep['sampled_observations']:
                self.assertEqual(git_blob(row['source_path']), row['source_blob_sha'])
                source = read(row['source_path'])
                self.assertEqual(row['source_available_at_utc'], source['evaluated_at_utc'])
                self.assertEqual(row['capture_cycle_time_ct'], source['generated_from_capture_time_ct'])

    def test_all_target_records_accounted_without_duplicate_episodes(self):
        episodes = self.review['episodes']
        self.assertEqual(len({(e['local_date_ct'], e['independent_site_group']) for e in episodes}), 4)
        totals = [0, 0, 0]
        for ep in episodes:
            expected = set()
            for path in (ROOT / 'model_data/observation_records').glob('*.json'):
                source = json.loads(path.read_text())
                if (source.get('generated_from_capture_time_ct') or '').startswith(ep['local_date_ct']) and source['cycle_in_target_predawn_dawn_window']:
                    expected.add(str(path.relative_to(ROOT)))
            rows = ep['sampled_observations']
            self.assertEqual({r['source_path'] for r in rows}, expected)
            self.assertEqual(len(rows), len(expected))
            counts = [len(rows), sum(r['event_label'] == 'observed_non_event_visible_scope' for r in rows), sum(r['event_label'] == 'unknown' for r in rows)]
            self.assertEqual(counts, [ep['record_counts'][k] for k in ['all_target_window_records', 'observed_non_event_visible_scope', 'unknown']])
            totals = [a+b for a,b in zip(totals, counts)]
            for excluded in ep['outside_window_records']:
                self.assertFalse(read(excluded['path'])['cycle_in_target_predawn_dawn_window'])
        self.assertEqual(totals, [48, 23, 25])

    def test_labels_obey_detectability_and_time_scope(self):
        for ep in self.review['episodes']:
            self.assertTrue(set(self.contract['control_definition']['required']) <= ep.keys())
            self.assertEqual(ep['event_label'], 'unknown')
            for row in ep['sampled_observations']:
                source = read(row['source_path'])
                cell = next(c for c in source['cells'] if c['shoreline_cell'] == 'Montrose')
                primary = next(c for c in cell['camera_rows'] if c['camera_id'] == 'montrose_shoreline')
                self.assertIn(row['event_label'], self.contract['control_definition']['event_label_values'])
                times = [datetime.fromisoformat(t) for t in row['primary_frame_times_ct']]
                self.assertEqual(len(times), 3)
                self.assertTrue(all(datetime.fromisoformat(ep['predawn_window_start_ct']) <= t <= datetime.fromisoformat(ep['predawn_window_end_ct']) for t in times))
                self.assertTrue(all(5 <= (b-a).total_seconds() <= 30 for a,b in zip(times, times[1:])))
                if row['event_label'] == 'observed_non_event_visible_scope':
                    self.assertEqual(cell['control_eligibility'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
                    self.assertTrue(primary['capture_ok'])
                    self.assertEqual(primary['integrity_issues'], [])
                    self.assertIn(primary['detectability'], ['moderate', 'high'])
                    self.assertIn(primary['visibility'], ['fair', 'good'])
                    self.assertEqual(primary['overall_visual_signal'], 'none')
                else:
                    self.assertEqual(cell['control_eligibility'], 'UNKNOWN_PRIMARY_CONTACT_VIEW_INADEQUATE')
                    self.assertEqual(primary['detectability'], 'low')
        row = next(r for ep in self.review['episodes'] for r in ep['sampled_observations'] if r['capture_cycle_time_ct'].startswith('2026-09-26T07:18:'))
        self.assertEqual(row['event_label'], 'unknown')

    def test_matching_public_gaps_and_leakage_prevent_promotion(self):
        self.assertEqual(self.review['production_action'], 'NO_CHANGE')
        self.assertEqual(self.review['summary']['fully_verified_tier_a_controls'], 0)
        self.assertEqual(self.review['summary']['held_out_calibration'], 'NOT_ESTIMABLE')
        public = read('model_data/public_camera_observation_log.json')
        for ep in self.review['episodes']:
            self.assertEqual(set(ep['matching_dimensions']), set(self.contract['matching_dimensions']))
            self.assertFalse(ep['fully_verified_matched_control'])
            self.assertIsNone(ep['matched_event_id'])
            self.assertFalse(ep['search_absence_is_negative'])
            self.assertEqual(ep['independent_human_non_event_confirmation'], 'NOT_VERIFIED')
            for row in ep['sampled_observations']:
                self.assertFalse(row['matched_control_eligible'])
                self.assertFalse(row['forecast_predictor_eligible'])
            for row in ep['public_camera_evidence']['records']:
                _, array, index = row['json_pointer'].split('/')
                actual = public[array][int(index)]
                self.assertFalse(actual['training_control_eligible'])
                self.assertEqual(row['camera_id'], actual['camera_id'])
                self.assertEqual(row['visible_scope'], actual['visible_scope'])
                self.assertIsNone(row['source_capture_time'])
        gaps = [s for s in self.review['web_review']['sources'] if s['evidence_use'] == 'VERIFICATION_GAP']
        self.assertTrue(any('facebook.com' in s['url'] for s in gaps))
        self.assertTrue(any('nextdoor.com' in s['url'] for s in gaps))
        self.assertTrue(all(s['dates_covered'] == [] for s in gaps))


if __name__ == '__main__':
    unittest.main()

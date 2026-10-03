import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('coverage_audit', Path(__file__).resolve().parents[1]/'model_data/audit_event_window_coverage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def record(t, **changes):
    camera = dict(camera_id='montrose_shoreline', capture_ok=True, integrity_issues=[], visibility='good', detectability='high')
    camera.update(changes)
    return dict(generated_from_capture_time_ct=t, cells=[dict(camera_rows=[camera])])


class CoverageTests(unittest.TestCase):
    def test_cross_midnight_and_deduplication(self):
        a = record('2026-10-02T22:06:00-05:00')
        b = record('2026-10-03T00:06:00-05:00')
        r = m.audit([a, a, b], '2026-10-02', '2026-10-03T12:00:00-05:00')
        w = r['windows'][2]
        self.assertEqual(w['retained_effort_records'], 2)
        self.assertEqual(w['cameras'][0]['usable_effort_samples'], 2)
        self.assertEqual(w['cameras'][0]['maximum_unsampled_elapsed_gap_minutes'], 174)
        self.assertEqual(r['whole_day_outcome'], 'UNKNOWN')

    def test_dark_failed_unverified_and_future_are_not_usable(self):
        r = m.audit([record('2026-10-02T16:06:00-05:00', detectability='low'),
                     record('2026-10-02T17:06:00-05:00', capture_ok=False),
                     record('2026-10-02T18:06:00-05:00', integrity_issues=None),
                     record('2026-10-02T19:06:00-05:00')],
                    '2026-10-02', '2026-10-02T18:30:00-05:00')
        self.assertEqual(r['windows'][0]['cameras'][0]['usable_effort_samples'], 0)
        self.assertEqual(r['windows'][0]['cameras'][0]['maximum_unsampled_elapsed_gap_minutes'], 210)
        self.assertFalse(r['windows'][0]['window_elapsed'])
        self.assertIsNone(r['windows'][2]['cameras'][0]['maximum_unsampled_elapsed_gap_minutes'])

    def test_missing_records_and_conflicts(self):
        r = m.audit([], '2026-10-02', '2026-10-03T12:00:00-05:00')
        self.assertEqual(r['windows'][1]['cameras'][0]['maximum_unsampled_elapsed_gap_minutes'], 390)
        self.assertEqual(r['clean_training_negative_count'], 0)
        with self.assertRaises(ValueError):
            m.audit([record('2026-10-02T16:06:00-05:00'), record('2026-10-02T16:06:00-05:00', capture_ok=False)], '2026-10-02', '2026-10-03T12:00:00-05:00')
        with self.assertRaises(ValueError):
            m.audit([record('2026-10-02T16:06:00')], '2026-10-02', '2026-10-03T12:00:00-05:00')

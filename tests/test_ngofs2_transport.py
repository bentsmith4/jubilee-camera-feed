import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'model_data' / 'ingest_ngofs2_point_clear.py'
spec = importlib.util.spec_from_file_location('ngofs2', MODULE_PATH)
ngofs2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ngofs2)


class NGOFS2TransportTests(unittest.TestCase):
    def test_shoreward_projection_east(self):
        self.assertAlmostEqual(ngofs2.shoreward_component(0.25, 0.0, 90), 0.25, places=7)
        self.assertAlmostEqual(ngofs2.shoreward_component(-0.25, 0.0, 90), -0.25, places=7)
        self.assertAlmostEqual(ngofs2.shoreward_component(0.0, 0.4, 90), 0.0, places=7)

    def test_vertical_indices_follow_fvcom_sigma_sign(self):
        surface, bottom = ngofs2.choose_vertical_indices([-0.9875, -0.75, -0.25, -0.0125])
        self.assertEqual(surface, 3)
        self.assertEqual(bottom, 0)

    def test_station_name_resolution_is_unique(self):
        names = ['Mobile Bay Light', 'Point Clear', 'Weeks Bay']
        self.assertEqual(ngofs2.find_station_index(names), 1)
        with self.assertRaises(ValueError):
            ngofs2.find_station_index(['Point Clear A', 'Point Clear B'])

    def test_latest_cycle_has_posting_cushion(self):
        now = datetime(2026, 9, 7, 4, 20, tzinfo=timezone.utc)
        cycles = ngofs2.cycle_candidates(now, count=2)
        self.assertEqual(cycles[0], datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc))
        now_too_early = datetime(2026, 9, 7, 3, 45, tzinfo=timezone.utc)
        self.assertEqual(ngofs2.cycle_candidates(now_too_early, count=1)[0], datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc))

    def test_trapezoid_integral(self):
        t0 = datetime(2026, 9, 7, 0, 0, tzinfo=timezone.utc)
        points = [(t0, 0.1), (t0.replace(minute=6), 0.1), (t0.replace(minute=12), 0.1)]
        self.assertAlmostEqual(ngofs2.integrate_trapezoid(points), 72.0, places=6)


if __name__ == '__main__':
    unittest.main()

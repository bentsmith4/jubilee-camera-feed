import importlib.util
from datetime import datetime, timedelta, timezone
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

    def test_longitude_normalization_preserves_point_clear(self):
        self.assertAlmostEqual(ngofs2.normalize_lon(272.06378173828125), -87.93621826171875, places=8)
        self.assertAlmostEqual(ngofs2.normalize_lon(-87.93453), -87.93453, places=8)

    def test_vertical_indices_follow_fvcom_sigma_sign(self):
        surface, bottom = ngofs2.choose_vertical_indices([-0.9875, -0.75, -0.25, -0.0125])
        self.assertEqual(surface, 3)
        self.assertEqual(bottom, 0)

    def test_station_name_resolution_is_unique(self):
        names = ['Mobile Bay Light', 'Point Clear', 'Weeks Bay']
        self.assertEqual(ngofs2.find_station_index(names), 1)
        with self.assertRaises(ValueError):
            ngofs2.find_station_index(['Point Clear A', 'Point Clear B'])

    def test_coordinate_fallback_is_bounded_and_auditable(self):
        names = ['8730001', '8733821', '8739999']
        lats = [30.2, ngofs2.TARGET_LAT + 0.001, 30.8]
        lons = [-88.1, 272.064, -87.7]
        idx, basis = ngofs2.resolve_station_index(names, lats, lons)
        self.assertEqual(idx, 1)
        self.assertEqual(basis, 'nearest_verified_coordinate')
        with self.assertRaises(ValueError):
            ngofs2.resolve_station_index(['x'], [31.0], [-89.0])

    def test_latest_cycle_has_posting_cushion(self):
        now_after_cushion = datetime(2026, 9, 7, 4, 31, tzinfo=timezone.utc)
        cycles = ngofs2.cycle_candidates(now_after_cushion, count=2)
        self.assertEqual(cycles[0], datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc))
        now_before_cushion = datetime(2026, 9, 7, 4, 20, tzinfo=timezone.utc)
        self.assertEqual(ngofs2.cycle_candidates(now_before_cushion, count=1)[0], datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc))

    def test_trapezoid_integral_and_coverage(self):
        t0 = datetime(2026, 9, 7, 0, 0, tzinfo=timezone.utc)
        points = [(t0, 0.1), (t0 + timedelta(minutes=6), 0.1), (t0 + timedelta(minutes=12), 0.1)]
        displacement, covered = ngofs2.integrate_trapezoid(points)
        self.assertAlmostEqual(displacement, 72.0, places=6)
        self.assertEqual(covered, 720.0)

    def test_forward_transport_is_not_antecedent_transport(self):
        t0 = datetime(2026, 9, 7, 0, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(0, 13):
            rows.append({'vertical_role': 'bottom', 'parameter': 'shoreward_current',
                         'valid_at': (t0 + timedelta(minutes=10*i)).isoformat(), 'value': 0.1})
        forward = ngofs2.summarize_forward_transport(rows, t0)
        self.assertAlmostEqual(forward['1']['signed_transport_m'], 360.0, places=6)
        self.assertAlmostEqual(forward['1']['coverage_fraction'], 1.0, places=6)
        self.assertGreater(forward['1']['signed_transport_m'], 0)


if __name__ == '__main__':
    unittest.main()

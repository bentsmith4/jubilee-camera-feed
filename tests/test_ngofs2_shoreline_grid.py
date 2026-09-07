import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'model_data' / 'ingest_ngofs2_shoreline_grid.py'
spec = importlib.util.spec_from_file_location('ngofs2_grid', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NGOFS2ShorelineGridTests(unittest.TestCase):
    def test_westward_destination_moves_offshore(self):
        lat, lon = mod.destination(30.525, -87.91492, 270.0, 1.0)
        self.assertAlmostEqual(lat, 30.525, places=3)
        self.assertLess(lon, -87.91492)

    def test_shoreward_projection_east(self):
        self.assertAlmostEqual(mod.shoreward_component(0.2, 0.0, 90.0), 0.2, places=7)
        self.assertAlmostEqual(mod.shoreward_component(-0.2, 0.0, 90.0), -0.2, places=7)
        self.assertAlmostEqual(mod.shoreward_component(0.0, 0.3, 90.0), 0.0, places=7)

    def test_transport_integration_records_gap_quality(self):
        t0 = datetime(2026, 9, 7, 3, tzinfo=timezone.utc)
        pts = [(t0 + timedelta(hours=i), 0.1) for i in range(4)]
        result = mod.integrate_transport(pts, t0, t0 + timedelta(hours=3))
        self.assertAlmostEqual(result['signed_transport_m'], 1080.0, places=5)
        self.assertEqual(result['quality'], 'good')
        sparse = [(t0, 0.1), (t0 + timedelta(hours=3), 0.1)]
        result = mod.integrate_transport(sparse, t0, t0 + timedelta(hours=3))
        self.assertEqual(result['quality'], 'coarse')

    def test_targets_use_public_coordinates(self):
        targets = mod.load_targets()
        self.assertEqual(len(targets), 6)
        montrose = next(x for x in targets if x['cell'] == 'Montrose')
        self.assertIn('public', montrose['coordinate_basis'].lower())
        self.assertIsNotNone(montrose['lat'])
        self.assertIsNotNone(montrose['lon'])


if __name__ == '__main__':
    unittest.main()

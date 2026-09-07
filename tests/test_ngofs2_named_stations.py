import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'model_data' / 'ingest_ngofs2_mobile_bay_named_stations.py'
spec = importlib.util.spec_from_file_location('ngofs2_named', MODULE_PATH)
ngofs2_named = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ngofs2_named)


class NGOFS2NamedStationResolutionTests(unittest.TestCase):
    def test_exact_station_id_is_resolved_before_proxy(self):
        names = ['8733821 Pt Clear, MB', 'NEAR FLY PROXY', '8732828 Weeks Bay, A']
        point_clear = next(x for x in ngofs2_named.TARGETS if x['station_id'] == '8733821')
        fly_creek = next(x for x in ngofs2_named.TARGETS if x['station_id'] == '8733502')
        self.assertEqual(ngofs2_named.resolve_exact(point_clear, names), (0, 'station_id'))
        self.assertIsNone(ngofs2_named.resolve_exact(fly_creek, names))

    def test_proxy_cannot_steal_reserved_exact_index(self):
        fly_creek = next(x for x in ngofs2_named.TARGETS if x['station_id'] == '8733502')
        # Index 0 is geographically nearest to Fly Creek but represents the
        # exact Point Clear model station and is therefore reserved.
        lats = [30.4890, 30.5500, 30.20]
        lons = [-87.9362, -87.9050, -88.20]
        idx, basis = ngofs2_named.resolve_proxy(fly_creek, lats, lons, excluded_indices={0})
        self.assertEqual(idx, 1)
        self.assertEqual(basis, 'nearest_verified_coordinate')

    def test_proxy_fails_instead_of_reusing_reserved_station(self):
        fly_creek = next(x for x in ngofs2_named.TARGETS if x['station_id'] == '8733502')
        with self.assertRaises(ValueError):
            ngofs2_named.resolve_proxy(fly_creek, [30.4890, 31.2], [-87.9362, -89.0], excluded_indices={0})


if __name__ == '__main__':
    unittest.main()

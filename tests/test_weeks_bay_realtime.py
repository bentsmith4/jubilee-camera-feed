import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'model_data' / 'ingest_weeks_bay_realtime.py'
spec = importlib.util.spec_from_file_location('weeks_bay', MODULE_PATH)
weeks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(weeks)


class WeeksBayRealtimeTests(unittest.TestCase):
    def setUp(self):
        self.retrieved = datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc)

    def test_ocean_station_specific_ndbc_format(self):
        payload = '''#YY  MM DD hh mm DEPTH OTMP COND SAL O2% O2PPM CLCON TURB PH EH\n#yr  mo dy hr mn m degC mS/cm psu % ppm ug/l FTU - mv\n2026 09 06 15 00 2.3 31.3 26.55 14.20 39.3 2.70 MM 35 7.40 MM\n'''
        rows = weeks.parse_ocean(payload, self.retrieved)
        by_parameter = {r['parameter']: r for r in rows}
        self.assertEqual(by_parameter['dissolved_oxygen']['value'], 2.70)
        self.assertEqual(by_parameter['dissolved_oxygen']['unit'], 'mg/L')
        self.assertEqual(by_parameter['salinity']['value'], 14.20)
        self.assertEqual(by_parameter['water_temperature']['value'], 31.3)
        self.assertEqual(by_parameter['dissolved_oxygen']['depth_m'], 2.3)
        self.assertEqual(by_parameter['dissolved_oxygen']['evidence_class'], 'DIRECT_STATION_PROXY_EASTERN_SHORE')
        self.assertEqual(by_parameter['dissolved_oxygen']['production_weight'], 0.0)
        self.assertEqual(by_parameter['dissolved_oxygen']['available_at'], self.retrieved.isoformat())

    def test_met_station_specific_ndbc_format(self):
        payload = '''#YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE\n#yr mo dy hr mn degT m/s m/s m sec sec degT hPa degC degC degC nmi hPa ft\n2026 09 07 02 45 MM 0.0 MM MM MM MM MM 1011.0 26.9 MM 25.5 MM MM MM\n2026 09 07 00 15 220 0.5 MM MM MM MM MM 1010.0 29.6 MM 25.0 MM MM MM\n'''
        rows = weeks.parse_met(payload, self.retrieved)
        self.assertTrue(any(r['parameter'] == 'wind_speed' and r['value'] == 0.0 for r in rows))
        self.assertTrue(any(r['parameter'] == 'wind_direction' and r['value'] == 220.0 for r in rows))
        self.assertTrue(all(r['production_weight'] == 0.0 for r in rows))
        self.assertTrue(all(r['station_id'] == 'WKXA1' for r in rows))

    def test_missing_values_are_not_coerced(self):
        payload = '''#YY MM DD hh mm DEPTH OTMP COND SAL O2% O2PPM CLCON TURB PH EH\n#yr mo dy hr mn m degC mS/cm psu % ppm ug/l FTU - mv\n2026 09 06 15 00 2.3 31.3 MM 14.20 MM MM MM MM 7.40 MM\n'''
        rows = weeks.parse_ocean(payload, self.retrieved)
        params = {r['parameter'] for r in rows}
        self.assertNotIn('dissolved_oxygen', params)
        self.assertIn('salinity', params)
        self.assertIn('water_temperature', params)


if __name__ == '__main__':
    unittest.main()

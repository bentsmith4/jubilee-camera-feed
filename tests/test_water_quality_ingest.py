import csv
import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
import ingest_water_quality as ingest

class IngestTests(unittest.TestCase):
    def payload(self, **changes):
        row = {'MonitoringLocationIdentifier': 's', 'CharacteristicName': 'Enterococcus',
               'ActivityStartDate': '2026-08-29', 'ActivityStartTime/Time': '07:00:00',
               'ActivityStartTime/TimeZoneCode': 'CDT', 'ResultMeasureValue': '10',
               'ResultMeasure/MeasureUnitCode': 'MPN/100mL', 'ResultStatusIdentifier': 'Final'}
        row.update(changes)
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=list(row))
        writer.writeheader(); writer.writerow(row)
        return text.getvalue().encode()
    def normalize(self, **changes):
        return ingest.normalize(self.payload(**changes), 'test', {'s': 'Fairhope'},
                                'https://example.org/result', '2026-09-06T20:00:00+00:00')[0]
    def test_error_page_is_not_data(self):
        with self.assertRaises(ValueError):
            ingest.read_csv(b'<html>temporarily unavailable</html>', ('MonitoringLocationIdentifier',))
    def test_units_preserved(self):
        self.assertEqual(self.normalize()['unit'], 'MPN/100mL')
    def test_less_than_not_exact_value(self):
        row = self.normalize(ResultMeasureValue='<10')
        self.assertIsNone(row['value'])
        self.assertEqual(row['value_qualifier'], '<')
    def test_detection_not_overwritten_by_final_status(self):
        row = self.normalize(ResultDetectionConditionText='Not Detected')
        self.assertEqual(row['qc_or_status'], 'Final')
        self.assertEqual(row['detection_condition'], 'Not Detected')
    def test_known_timezone(self):
        self.assertEqual(self.normalize()['sample_datetime_utc'], '2026-08-29T12:00:00+00:00')
    def test_unknown_timezone_not_guessed(self):
        row = self.normalize(**{'ActivityStartTime/TimeZoneCode': ''})
        self.assertIsNone(row['sample_datetime_utc'])
    def test_stable_observation_id(self):
        a = self.normalize()
        b = ingest.normalize(self.payload(), 'test', {'s': 'Fairhope'}, 'https://example.org/result',
                             '2026-09-07T20:00:00+00:00')[0]
        self.assertEqual(a['observation_id'], b['observation_id'])
    def test_missing_depth_not_surface_or_bottom(self):
        row = self.normalize()
        self.assertIsNone(row['depth'])
        self.assertEqual(row['production_weight'], 0)
    def test_new_station_rejected(self):
        with self.assertRaises(ValueError):
            self.normalize(MonitoringLocationIdentifier='unexpected')
    def test_station_coordinates_from_metadata(self):
        row = ingest.normalize(self.payload(), 'test', {'s': 'Fairhope'}, 'source', 'time',
                               {'s': {'LatitudeMeasure': '30.5', 'LongitudeMeasure': '-87.9'}})[0]
        self.assertEqual(row['latitude'], 30.5)
        self.assertEqual(row['longitude'], -87.9)

if __name__ == '__main__':
    unittest.main()

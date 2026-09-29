import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
from research_river_bay_lag_2016 import daily_discharge, matlab_utc, window, compare


class RiverBayLagResearchTests(unittest.TestCase):
    def test_antecedent_never_reads_target_or_future(self):
        target = date(2016, 7, 20)
        data = {target - timedelta(days=i): {'cfs': float(i)} for i in range(15)}
        self.assertEqual(window(data, target, 1, 3), 1.5)
        data[target]['cfs'] = 999999
        data[target + timedelta(days=1)] = {'cfs': 999999}
        self.assertEqual(window(data, target, 1, 3), 1.5)
        del data[target - timedelta(days=2)]
        self.assertIsNone(window(data, target, 1, 3))

    def test_historical_hourly_coverage_and_qualifiers(self):
        day = datetime(2016, 7, 20, tzinfo=timezone.utc)
        def record(hour, method='m', value=100, eligible=True):
            return {'station_id': '02469761', 'parameter_code': '00060',
                    'research_qc_eligible': eligible, 'unit': 'ft3/s',
                    'series_id': method, 'observed_at_utc': (day + timedelta(hours=hour)).isoformat(),
                    'value': value, 'is_estimated': True, 'qualifiers': 'A|e'}
        records = [record(h) for h in range(24)]
        daily, coverage = daily_discharge(records, '02469761')
        self.assertEqual(coverage['complete_utc_days'], 1)
        self.assertEqual(daily[day.date()]['estimated_samples'], 24)
        records = [r for i, r in enumerate(records) if i not in (5, 6, 7)]
        self.assertEqual(daily_discharge(records, '02469761')[0], {})
        self.assertEqual(daily_discharge([record(0, 'pool'), record(1, 'tailwater')], '02469761')[1]['status'],
                         'AMBIGUOUS_OR_MISSING_METHOD')

    def test_cdt_and_cst_source_labels_are_distinct(self):
        ordinal = datetime(2016, 7, 14).toordinal() + 366
        self.assertEqual(matlab_utc(ordinal, 5), datetime(2016, 7, 14, 5))
        self.assertEqual(matlab_utc(ordinal, 6), datetime(2016, 7, 14, 6))

    def test_short_or_missing_record_refuses_model_fit(self):
        day = date(2016, 7, 14)
        bay = {day + timedelta(days=i): {'01': {'oxygen_percent_median': 20}}
               for i in range(10)}
        self.assertEqual(compare({}, bay, '02428400', (1, 3))['status'], 'INSUFFICIENT_OVERLAP')


if __name__ == '__main__':
    unittest.main()

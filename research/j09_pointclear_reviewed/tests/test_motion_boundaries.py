"""Synthetic boundary tests; these fixtures are not environmental evidence."""
import csv
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'motion_consistency.py'

class MotionBoundaryTests(unittest.TestCase):
    def run_case(self, count, speed=1):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nav = []
            ensembles = []
            for i in range(count):
                stamp = f'2010-08-18T12:00:{i:02d}+00:00'
                nav.append(dict(survey_date='2010-08-18', observed_at_utc=stamp,
                    qc_flags='', vessel_speed_over_ground_mps=speed))
                ensembles.append(dict(survey_date='2010-08-18', ensemble_number=i,
                    gps_gga_utc_candidate=stamp, external_rmc_nearest_seconds='0',
                    external_rmc_separation_m='0', bottom_v1_mps='1', bottom_v2_mps='0',
                    bottom_error_mps='', coordinate_system='SHIP'))
            columns = {'navigation_rmc.csv.gz': (nav, ['survey_date','observed_at_utc','qc_flags','vessel_speed_over_ground_mps']),
                'ensembles.csv.gz': (ensembles, ['survey_date','ensemble_number','gps_gga_utc_candidate',
                    'external_rmc_nearest_seconds','external_rmc_separation_m','bottom_v1_mps','bottom_v2_mps',
                    'bottom_error_mps','coordinate_system'])}
            for name, (rows, fields) in columns.items():
                with gzip.open(root/name,'wt',newline='') as output:
                    writer=csv.DictWriter(output,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            result=subprocess.run([sys.executable,str(SCRIPT),'--results-dir',str(root)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            summary=json.loads((root/'motion_consistency.json').read_text())
            self.assertEqual(summary['all_pairs']['n'],count)
            self.assertEqual(summary['production_action'],'NO_CHANGE')
            self.assertTrue((root/'motion_pairs.csv').read_text().startswith('survey_date,'))
            return summary

    def test_empty_selection_preserves_report(self):
        self.run_case(0)

    def test_single_pair_correlation_is_unknown(self):
        self.assertIsNone(self.run_case(1)['all_pairs']['pearson_speed_correlation'])

    def test_constant_speed_correlation_is_unknown(self):
        self.assertIsNone(self.run_case(3)['all_pairs']['pearson_speed_correlation'])

if __name__ == '__main__': unittest.main()

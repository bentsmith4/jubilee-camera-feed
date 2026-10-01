"""Coverage integrity gates; no live network or implementation-mirroring fits."""
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

P=Path(__file__).resolve().parents[1]/'model_data/independent_river_validation/audit.py'
spec=importlib.util.spec_from_file_location('river_coverage_audit',P)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class IndependentCoverageTests(unittest.TestCase):
    def test_utc_boundary_and_naive_refusal(self):
        self.assertEqual(audit.stamp('2018-05-01T23:30:00-05:00').day,2)
        with self.assertRaises(ValueError):audit.stamp('2018-05-01T00:00:00')

    def test_dense_cluster_is_not_full_day(self):
        t=datetime(2018,5,1,tzinfo=timezone.utc)
        self.assertFalse(audit.complete([t+timedelta(minutes=i) for i in range(43)],43,3600))
        self.assertTrue(audit.complete([t+timedelta(minutes=30*i) for i in range(48)],43,3600))
        self.assertFalse(audit.complete([t]*48,43,3600))

    def test_bad_flags_and_conflicting_duplicates_do_not_pass(self):
        t=datetime(2017,5,1,tzinfo=timezone.utc)
        rows=[{'ts':(t+timedelta(minutes=30*i)).isoformat(),'dis_oxy1_avg':'50','dis_oxy1flag':'3'} for i in range(48)]
        for i in range(5):rows[i]['dis_oxy1flag']='2'
        rows.append(dict(rows[6],dis_oxy1_avg='90'))
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'data.zip';s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            with zipfile.ZipFile(f,'w') as z:z.writestr('data.csv',s.getvalue())
            daily,report=audit.annual(f,{'oxygen':audit.HYDRO['oxygen']},2017,'hydro')
        self.assertEqual(daily['oxygen'],{})
        self.assertEqual(report['variables']['oxygen']['conflicting_timestamps'],1)
        self.assertEqual(report['counts']['oxygen_rejected_qc_or_range'],5)

    def test_missing_antecedent_not_imputed(self):
        start=datetime(2018,5,1).date();days=[start+timedelta(days=i) for i in range(153)]
        h={'oxygen':dict.fromkeys(days,1)};m={'wind_vector':dict.fromkeys(days,1)}
        f={start+timedelta(days=i):100 for i in range(-14,153)}
        full=audit.overlap(h,m,f,2018,[7,8,9,10,11,12,13])
        self.assertEqual(full['common_days'],153)
        del f[start-timedelta(days=13)]
        reduced=audit.overlap(h,m,f,2018,[7,8,9,10,11,12,13])
        self.assertEqual(reduced['common_days'],152)
        self.assertNotIn(start.isoformat(),reduced['dates'])

class ScoringIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0,str(P.parent))
        import score
        cls.score=score

    def test_test_rows_do_not_change_training_fit(self):
        import numpy as np
        first,fit1=self.score.ridge([[0],[1],[2]],[1,2,3],[[3]])
        second,fit2=self.score.ridge([[0],[1],[2]],[1,2,3],[[3],[1000000]])
        self.assertEqual(fit1,fit2)
        self.assertAlmostEqual(first[0],second[0])

    def test_error_sign_and_block_pairing(self):
        days=[datetime(2018,5,1).date()+timedelta(days=i) for i in range(28)]
        r=self.score.paired_metrics(days,[0]*28,[2]*28,[1]*28)
        self.assertEqual(r['delta_mse'],-3)
        self.assertEqual(len(r['blocks']),2)
        self.assertEqual(r['delta_mse_97_5_percent_block_percentile_interval'],[-3,-3])

if __name__=='__main__':unittest.main()

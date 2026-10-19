import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'model_data'))
from replay_wind_cadence import sector, state_at, profile, qualify, select_skips

class WindReplayTests(unittest.TestCase):
    def setUp(self):
        self.t=datetime(2026,10,1,12,tzinfo=timezone.utc)
    def row(self,minutes,speed=16,direction=0,lag=5):
        t=self.t+timedelta(minutes=minutes)
        return dict(observed=t,received=t+timedelta(minutes=lag),speed=speed,direction=direction)
    def test_disjoint_sector_boundaries(self):
        self.assertEqual([sector(x) for x in (0,44.9,45,89.9,90,314.9,315,360)],
                         ['north','north','northeast','northeast','other','other','north','north'])
    def test_future_receipt_and_staleness(self):
        r=self.row(0)
        self.assertIsNone(state_at([r],self.t))
        self.assertIsNotNone(state_at([r],self.t+timedelta(minutes=90)))
        self.assertIsNone(state_at([r],self.t+timedelta(minutes=90,microseconds=1)))
    def test_unknown_latest_cannot_backfill(self):
        self.assertIsNone(state_at([self.row(-60),self.row(0,speed=None)],self.t+timedelta(minutes=6)))
    def test_conflicting_report_rejected(self):
        self.assertIsNone(state_at([self.row(0),self.row(0,speed=20)],self.t+timedelta(minutes=6)))
    def test_brief_direction_shift_breaks_persistence(self):
        s={'A':[self.row(-120),self.row(-60),self.row(-30,direction=70),self.row(-20)]}
        self.assertFalse(qualify(profile(s,self.t,1,('A',)),15,'north'))
        self.assertTrue(qualify(profile(s,self.t,1,('A',)),10,'any'))
    def test_missing_station_and_expiry_gap(self):
        self.assertIsNone(profile({'A':[self.row(-180),self.row(-20)]},self.t,2,('A',)))
        self.assertIsNone(profile({'A':[]},self.t,1,('A',)))
    def test_skip_counts_reset_after_protection(self):
        self.assertEqual(select_skips([True]*8,.25),[3,7])
        self.assertEqual(select_skips([True,False,True,True],.5),[3])
        for f in (.25,.5,.75):
            self.assertEqual(len(select_skips([True]*100,f)),100*f)

if __name__=='__main__':unittest.main()

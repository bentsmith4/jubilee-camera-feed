import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))
import sys,types,unittest
from datetime import datetime,timedelta,timezone
sys.modules['refresh_all']=types.SimpleNamespace()
from capture_service import slot

class Schedule(unittest.TestCase):
    def test_hour_boundary(self):
        start=datetime(2026,9,6,4,6,25,tzinfo=timezone.utc);end=start+timedelta(hours=4)
        now=start.replace(hour=17,minute=5,second=59)
        self.assertIn('16:06:00',slot(now,start,end))
        self.assertIn('17:06:00',slot(now+timedelta(seconds=1),start,end))
    def test_twenty_minute_dawn_slots(self):
        start=datetime(2026,9,6,4,6,25,tzinfo=timezone.utc);end=start+timedelta(hours=4)
        self.assertEqual(slot(start,start,end),'dawn:2026-09-06:0')
        self.assertEqual(slot(start+timedelta(minutes=19),start,end),'dawn:2026-09-06:0')
        self.assertEqual(slot(start+timedelta(minutes=20),start,end),'dawn:2026-09-06:1')
        self.assertEqual(slot(end,start,end),'dawn:2026-09-06:12')
if __name__=='__main__':unittest.main()

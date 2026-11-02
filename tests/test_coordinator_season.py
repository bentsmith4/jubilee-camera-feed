import importlib.util
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1] / "desktop_runtime"
sys.path.insert(0, str(ROOT))
from seasonal_policy import TZ

class StopCycle(Exception):
    pass

class CoordinatorSeasonTests(unittest.TestCase):
    def run_cycle(self, now, after_capture=None):
        ra = types.SimpleNamespace(TZ=TZ, dawn_window=lambda: (now, now, now-timedelta(hours=1), now+timedelta(hours=1)))
        spec = importlib.util.spec_from_file_location("seasonal_coordinator", ROOT/"capture_service.py")
        m = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"refresh_all": ra}):
            spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            m.STATE = Path(tmp)/"state.json"
            m.STATE.write_text(json.dumps({"last_canonical_success": "prior-success"}))
            clock = [now]
            class Clock(datetime):
                @classmethod
                def now(cls, zone):
                    return clock[0].astimezone(zone)
            m.datetime = Clock
            def dispatch(script, limit):
                if script == "live_capture.py" and after_capture is not None:
                    clock[0] = after_capture
                return True
            m.execute = Mock(side_effect=dispatch)
            m.log = Mock()
            with patch.object(m.socket, "socket"), patch.object(m.time, "sleep", side_effect=StopCycle):
                with self.assertRaises(StopCycle):
                    m.main()
            return [call.args[0] for call in m.execute.call_args_list], json.loads(m.STATE.read_text())

    def test_offseason_skips_both_products_and_preserves_history(self):
        calls, state = self.run_cycle(datetime(2026, 11, 15, 0, tzinfo=TZ))
        self.assertEqual(calls, [])
        self.assertEqual(state["live_monitoring_status"], "offseason_not_monitored")
        self.assertEqual(state["last_canonical_success"], "prior-success")
        self.assertNotIn("canonical_slot", state)
        self.assertEqual(state["canonical_monitoring_status"], "offseason_not_monitored")

    def test_capture_crossing_midnight_does_not_launch_upload(self):
        calls, state = self.run_cycle(datetime(2026, 11, 14, 23, 59, 59, tzinfo=TZ),
                                     datetime(2026, 11, 15, 0, 0, 1, tzinfo=TZ))
        self.assertIn("live_capture.py", calls)
        self.assertNotIn("live_upload.py", calls)
        self.assertNotIn("last_live_success", state)
        self.assertEqual(state["live_monitoring_status"], "offseason_not_monitored")

    def test_inseason_preserves_canonical_and_live_dispatch(self):
        for now in (datetime(2026, 11, 14, 6, tzinfo=TZ), datetime(2027, 5, 18, 6, tzinfo=TZ)):
            with self.subTest(now=now):
                calls, state = self.run_cycle(now)
                self.assertEqual(calls, ["capture_publish.py", "live_capture.py", "live_upload.py"])
                self.assertIn("canonical_slot", state)

if __name__ == "__main__":
    unittest.main()

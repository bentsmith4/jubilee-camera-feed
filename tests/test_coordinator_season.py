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
    def run_cycle(self, now):
        ra = types.SimpleNamespace(TZ=TZ, dawn_window=lambda: (now, now, now-timedelta(hours=1), now+timedelta(hours=1)))
        spec = importlib.util.spec_from_file_location("seasonal_coordinator", ROOT/"capture_service.py")
        m = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"refresh_all": ra}):
            spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            m.STATE = Path(tmp)/"state.json"
            m.STATE.write_text(json.dumps({"last_canonical_success": "prior-success"}))
            m.execute = Mock(return_value=True)
            m.log = Mock()
            with patch.object(m.socket, "socket"), patch.object(m.time, "sleep", side_effect=StopCycle):
                with self.assertRaises(StopCycle):
                    m.main()
            return [call.args[0] for call in m.execute.call_args_list], json.loads(m.STATE.read_text())

    def test_offseason_skips_paid_pipeline_preserves_live_and_history(self):
        calls, state = self.run_cycle(datetime(2026, 2, 1, 6, tzinfo=TZ))
        self.assertEqual(calls, ["live_capture.py", "live_upload.py"])
        self.assertEqual(state["last_canonical_success"], "prior-success")
        self.assertNotIn("canonical_slot", state)
        self.assertEqual(state["canonical_monitoring_status"], "offseason_not_monitored")

    def test_inseason_preserves_canonical_and_live_dispatch(self):
        calls, state = self.run_cycle(datetime(2026, 9, 8, 6, tzinfo=TZ))
        self.assertEqual(calls, ["capture_publish.py", "live_capture.py", "live_upload.py"])
        self.assertIn("canonical_slot", state)

if __name__ == "__main__":
    unittest.main()

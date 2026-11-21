"""Exercise state recovery without contacting cameras or the deployed runtime."""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / "desktop_runtime"
sys.path.insert(0, str(ROOT))
from seasonal_policy import TZ


class StopCycle(Exception):
    pass


class CoordinatorRecoveryTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 9, 28, 10, 25, tzinfo=TZ)
        self.now = now
        dawn = now.replace(hour=6, minute=19)
        ra = types.SimpleNamespace(
            TZ=TZ,
            dawn_window=lambda: (self.now, dawn, dawn - timedelta(hours=2), dawn + timedelta(hours=2)),
        )
        spec = importlib.util.spec_from_file_location("recovery_coordinator", ROOT / "capture_service.py")
        self.service = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"refresh_all": ra}):
            spec.loader.exec_module(self.service)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.service.STATE = Path(tmp.name) / "state.json"
        self.service.execute = Mock(return_value=True)
        self.service.log = Mock()
        self.initial = {
            "canonical_slot": "hour:2026-09-28T10:06:00-05:00",
            "last_canonical_success": "2026-09-28T10:11:00-05:00",
        }

    def run_cycle(self, expected_exception=StopCycle):
        with patch.object(self.service.socket, "socket"), patch.object(
            self.service.time, "sleep", side_effect=StopCycle
        ), patch.object(self.service, "datetime", wraps=datetime) as clock:
            # Every season decision must use the fixture clock, not the CI date.
            clock.now.return_value = self.now
            with self.assertRaises(expected_exception):
                self.service.main()

    def test_corrupt_or_non_object_state_recovers(self):
        for content in (b'{"heartbeat":', b"\xff", b"[]", b"null", b'"text"'):
            with self.subTest(content=content):
                self.service.STATE.write_bytes(content)
                self.service.log.reset_mock()
                self.run_cycle()
                state = json.loads(self.service.STATE.read_text(encoding="utf-8"))
                self.assertIn("heartbeat", state)
                self.assertIn("last_canonical_success", state)
                self.service.log.assert_any_call("Coordinator state unreadable; rebuilding from fresh captures")

    def test_state_read_oserror_recovers_without_logging_exception(self):
        self.service.STATE.write_text("{}", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=OSError("private diagnostic")):
            self.run_cycle()
        self.service.log.assert_any_call("Coordinator state unreadable; rebuilding from fresh captures")
        self.assertNotIn("private diagnostic", str(self.service.log.call_args_list))
        self.assertIn("heartbeat", json.loads(self.service.STATE.read_text(encoding="utf-8")))

    def test_valid_legacy_state_migrates_without_duplicate_canonical_capture(self):
        self.service.STATE.write_text(json.dumps(self.initial), encoding="utf-8")
        self.run_cycle()
        state = json.loads(self.service.STATE.read_text(encoding="utf-8"))
        self.assertEqual(state["last_regular_slot"], self.initial["canonical_slot"])
        self.assertEqual(state["last_canonical_success"], self.initial["last_canonical_success"])
        self.assertEqual(
            [call.args[0] for call in self.service.execute.call_args_list],
            ["live_capture.py", "live_upload.py"],
        )

    def test_november_15_pauses_capture_and_preserves_last_success(self):
        self.now = datetime(2026, 11, 15, 10, 25, tzinfo=TZ)
        self.service.STATE.write_text(json.dumps(self.initial), encoding="utf-8")
        self.run_cycle()
        state = json.loads(self.service.STATE.read_text(encoding="utf-8"))
        self.service.execute.assert_not_called()
        self.assertEqual(state["canonical_monitoring_status"], "offseason_not_monitored")
        self.assertEqual(state["live_monitoring_status"], "offseason_not_monitored")
        self.assertEqual(state["last_canonical_success"], self.initial["last_canonical_success"])
        self.assertEqual(state["heartbeat"], self.now.isoformat())

    def test_state_is_flushed_and_synced_before_replacing_previous_snapshot(self):
        self.service.STATE.write_text(json.dumps(self.initial), encoding="utf-8")
        original = self.service.STATE.read_bytes()
        real_fsync = os.fsync

        def inspect_then_sync(fd):
            self.assertEqual(self.service.STATE.read_bytes(), original)
            pending = json.loads(self.service.STATE.with_suffix(".tmp").read_text(encoding="utf-8"))
            self.assertIn("heartbeat", pending)
            real_fsync(fd)

        with patch.object(self.service.os, "fsync", side_effect=inspect_then_sync) as sync:
            self.run_cycle()
        sync.assert_called_once()
        self.assertIn("heartbeat", json.loads(self.service.STATE.read_text(encoding="utf-8")))
        self.assertFalse(self.service.STATE.with_suffix(".tmp").exists())

    def test_failed_sync_preserves_previous_state(self):
        self.service.STATE.write_text(json.dumps(self.initial), encoding="utf-8")
        original = self.service.STATE.read_bytes()
        with patch.object(self.service.os, "fsync", side_effect=OSError("sync failed")):
            self.run_cycle(expected_exception=OSError)
        self.assertEqual(self.service.STATE.read_bytes(), original)

    def test_success_clears_persisted_failure_count(self):
        self.service.STATE.write_text(json.dumps({"canonical_failures": 2}))
        self.run_cycle()
        state = json.loads(self.service.STATE.read_text())
        self.assertEqual(state["canonical_failures"], 0)
        self.assertIn("last_canonical_success", state)

    def test_failed_cycle_still_records_failure_and_backoff(self):
        self.service.STATE.write_text("{}")
        self.service.execute.side_effect = [False, True, True]
        self.run_cycle()
        state = json.loads(self.service.STATE.read_text())
        self.assertEqual(state["canonical_failures"], 1)
        self.assertNotIn("last_canonical_success", state)
        self.service.log.assert_any_call("Canonical failure; bounded backoff applied")

if __name__ == "__main__":
    unittest.main()

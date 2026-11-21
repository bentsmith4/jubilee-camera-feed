"""Offline subprocess fixtures; no installed runtime, cameras or paid APIs."""
import importlib.util
import io
import runpy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'desktop_runtime'
sys.path.insert(0, str(ROOT))
SECRET = 'rtsp://private.example/?token=SECRET'

class PipelineTimeoutTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('timeout_service', ROOT / 'capture_service.py')
        self.m = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'refresh_all': types.SimpleNamespace()}):
            spec.loader.exec_module(self.m)
        self.m.log = Mock()

    def test_timeout_retains_safe_stage_but_does_not_claim_cleanup(self):
        output = ('JUBILEE_STAGE burst_capture.py start\n'
                  'JUBILEE_STAGE burst_capture.py end\n'
                  'JUBILEE_STAGE analyze_frames.py start\n' + SECRET + '\n'
                  'JUBILEE_STAGE '+SECRET+' start\n')
        process = Mock(pid=321, returncode=-9)
        process.communicate.side_effect = [subprocess.TimeoutExpired([SECRET], 900), (output, SECRET)]
        with patch.object(self.m.subprocess, 'Popen', return_value=process), patch.object(
            self.m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=5)
        ) as kill, patch.object(self.m.time, 'monotonic', side_effect=[10, 910]):
            self.assertFalse(self.m.execute('capture_publish.py', 900))
        process.communicate.assert_any_call(timeout=900)
        kill.assert_called_once_with(['taskkill', '/PID', '321', '/T', '/F'], capture_output=True)
        message = self.m.log.call_args.args[0]
        self.assertIn('active_stage=analyze_frames.py', message)
        self.assertIn('last_completed_stage=burst_capture.py', message)
        self.assertIn('taskkill_exit=5', message)
        self.assertIn('descendant_cleanup=unverified', message)
        self.assertIn('elapsed_seconds=900', message)
        self.assertNotIn(SECRET, message)

    def test_live_timeout_cannot_inherit_canonical_stage(self):
        self.m.timeout_diagnostic('live_capture.py', 'JUBILEE_STAGE analyze_frames.py start', 0, 0, 1)
        self.assertIn('active_stage=unknown', self.m.log.call_args.args[0])

    def test_missing_and_malformed_output_and_logging_failure_are_safe(self):
        for output in (None, SECRET, 'JUBILEE_STAGE burst_capture.py start '+SECRET):
            self.m.timeout_diagnostic(SECRET, output, 0, SECRET, SECRET)
            message = self.m.log.call_args.args[0]
            self.assertNotIn(SECRET, message)
            self.assertIn('active_stage=unknown', message)
        self.m.log.side_effect = OSError(SECRET)
        self.m.timeout_diagnostic('capture_publish.py', '', 0, 0, 1)

    def test_success_and_nonzero_results_remain_unchanged(self):
        for code in (0, 7):
            process = Mock(returncode=code)
            process.communicate.return_value = (SECRET, SECRET)
            with patch.object(self.m.subprocess, 'Popen', return_value=process):
                self.assertEqual(self.m.execute('capture_publish.py', 900), code == 0)
            self.assertNotIn(SECRET, str(self.m.log.call_args_list))

    def test_pipeline_emits_stage_before_child_and_keeps_command_order(self):
        output = io.StringIO()
        calls = []
        def child(command):
            name = Path(command[1]).name
            self.assertTrue(output.getvalue().endswith('JUBILEE_STAGE '+name+' start\n'))
            calls.append(command)
            return types.SimpleNamespace(returncode=0)
        with patch.dict(sys.modules, {'seasonal_policy': types.SimpleNamespace(require_season=lambda: None)}), patch(
            'socket.socket'
        ), patch('subprocess.run', side_effect=child), patch('sys.stdout', output):
            runpy.run_path(str(ROOT / 'capture_publish.py'))
        self.assertEqual([Path(c[1]).name for c in calls], [
            'burst_capture.py', 'analyze_frames.py', 'notify_alligator.py',
            'upload_frames.py', 'publish_github.py'])
        self.assertEqual(calls[0][2:], ['--force'])
        self.assertEqual(output.getvalue().count('JUBILEE_STAGE'), 10)

if __name__ == '__main__':
    unittest.main()

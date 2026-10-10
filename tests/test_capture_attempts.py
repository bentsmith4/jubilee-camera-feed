"""Canonical capture regressions; no camera, credentials or network access."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_runtime"))
from camera_policy import CAMERA_IDS
import capture_diagnostics as diagnostics
import publish_github

spec = importlib.util.spec_from_file_location("burst_attempt_test", ROOT / "desktop_runtime/burst_capture.py")
bc = importlib.util.module_from_spec(spec)
ra = types.ModuleType("refresh_all")
ra.TZ = ZoneInfo("America/Chicago")
with patch.dict(sys.modules, {"requests": Mock(), "refresh_all": ra,
                             "camera_lock": types.SimpleNamespace(serialized=lambda f: f),
                             "playwright": types.ModuleType("playwright"),
                             "playwright.sync_api": types.SimpleNamespace(sync_playwright=Mock())}):
    spec.loader.exec_module(bc)

SECRET = "rtsp://user:PASSWORD@private.example/video?token=SECRET"


class CaptureAttempts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.frames = self.base / "frames"
        self.burst = self.frames / "burst_latest"
        self.burst.mkdir(parents=True)
        for name, value in (("FRAMES", self.frames), ("BURST_DIR", self.burst),
                            ("STATUS_PATH", self.frames / "status.json"),
                            ("BURST_STATUS_PATH", self.frames / "burst_status.json")):
            p = patch.object(bc, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(bc.time, "sleep")
        self.sleep = p.start()
        self.addCleanup(p.stop)
        self.out = io.StringIO()
        p = contextlib.redirect_stdout(self.out)
        p.__enter__()
        self.addCleanup(p.__exit__, None, None, None)

    def error(self):
        return subprocess.CalledProcessError(1, ["ffmpeg", SECRET], stderr=(SECRET + " 503 Service Unavailable").encode())

    def assert_private_absent(self, text):
        for secret in ("PASSWORD", "SECRET", "private.example", "rtsp://"):
            self.assertNotIn(secret, text)

    def test_bounded_retry_for_all_six_and_partial_frames_discarded(self):
        for camera in CAMERA_IDS:
            with self.subTest(camera=camera):
                self.sleep.reset_mock()
                count = 0
                def capture(*args):
                    nonlocal count
                    count += 1
                    if count == 1:
                        (self.burst / (camera + "_1.jpg")).write_bytes(b"partial")
                        raise self.error()
                    self.assertFalse(list(self.burst.glob(camera + "_*.jpg")))
                    return [{"shot": n} for n in (1, 2, 3)]
                attempts = []
                with patch.object(bc, "capture_device_burst_once", side_effect=capture) as call:
                    shots = bc.capture_device_burst_with_retry(None, "TOKEN", {}, camera, ["RTSP"], attempts=attempts)
                self.assertEqual(call.call_count, 2)
                self.assertEqual(len(shots), 3)
                self.assertEqual(attempts, [{"attempt": 1, "ok": False, "category": "stream_unavailable", "returncode": 1},
                                            {"attempt": 2, "ok": True}])
                self.sleep.assert_called_once_with(8)
        self.assert_private_absent(self.out.getvalue())

    def test_exhaustion_preserves_original_exception_and_two_attempts(self):
        errors = [self.error(), self.error()]
        attempts = []
        with patch.object(bc, "capture_device_burst_once", side_effect=errors) as call:
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                bc.capture_device_burst_with_retry(None, "TOKEN", {}, "pcl_e3_bay_mouth", ["RTSP"], attempts=attempts)
        self.assertIs(caught.exception, errors[-1])
        self.assertEqual(call.call_count, 2)
        self.assertEqual([a["ok"] for a in attempts], [False, False])
        self.sleep.assert_called_once_with(8)
        self.assert_private_absent(json.dumps(attempts) + self.out.getvalue())

    def test_rtsp_retries_generate_and_stop_each_stream(self):
        response = Mock()
        response.json.return_value = {"results": {"streamUrls": {"rtspUrl": SECRET}, "streamExtensionToken": "SECRET"}}
        attempts = []
        with patch.object(bc.ra, "command_url", return_value="private-command", create=True), \
             patch.object(bc, "post_with_429_retry", return_value=response) as generate, \
             patch.object(bc.shutil, "which", return_value="ffmpeg"), \
             patch.object(bc.subprocess, "run", side_effect=self.error()) as run, \
             patch.object(bc.requests, "post") as stop, \
             patch.object(bc, "record_ffmpeg_failure") as local_log:
            with self.assertRaises(subprocess.CalledProcessError):
                bc.capture_device_burst_with_retry(None, "TOKEN", {}, "pcl_e3_bay_mouth", ["RTSP"], attempts=attempts)
        self.assertEqual((generate.call_count, run.call_count, stop.call_count, local_log.call_count), (2, 2, 2, 2))
        self.assertTrue(all(c.kwargs["timeout"] == 60 for c in run.call_args_list))
        self.assertTrue(all(c.kwargs["json"]["command"].endswith("StopRtspStream") for c in stop.call_args_list))

    def test_failed_e3_remains_failed_and_other_five_publish_normally(self):
        self.check_failed_feeds({'pcl_e3_bay_mouth'})

    def test_entire_montrose_site_failure_preserves_point_clear_capture(self):
        self.check_failed_feeds({c for c in CAMERA_IDS if c.startswith('montrose_')})

    def test_complete_camera_outage_publishes_failure_metadata_and_no_images(self):
        self.check_failed_feeds(set(CAMERA_IDS))

    def check_failed_feeds(self, failures):
        now = datetime.now(ra.TZ)
        browser = Mock()
        playwright = Mock()
        playwright.__enter__ = Mock(return_value=playwright)
        playwright.__exit__ = Mock(return_value=False)
        playwright.chromium.launch.return_value = browser
        def capture(browser, token, device, slug, proto):
            if slug in failures:
                raise self.error()
            shots = []
            for n in (1, 2, 3):
                file = self.burst / f"{slug}_{n}.jpg"
                file.write_bytes(b"\xff\xd8fixture\xff\xd9")
                shots.append({"shot": n, "timestamp_ct": now.isoformat(), "file": file.name, "bytes": file.stat().st_size})
            return shots
        with patch.multiple(ra, create=True, CAMERA_NAMES={c: c for c in CAMERA_IDS},
                            dawn_window=Mock(return_value=(now, now, now, now)),
                            load_credentials=Mock(), refresh_access_token=Mock(return_value="TOKEN"),
                            list_devices=Mock(return_value=list(CAMERA_IDS)), custom_name=lambda d: d,
                            protocols=lambda d: ["RTSP"]), \
             patch.object(bc, "sync_playwright", return_value=playwright), \
             patch.object(bc, "capture_device_burst_once", side_effect=capture) as call, \
             patch.object(sys, "argv", ["burst_capture.py", "--force"]):
            bc.main()
        status = json.loads(bc.STATUS_PATH.read_text())
        burst = json.loads(bc.BURST_STATUS_PATH.read_text())
        self.assertEqual(call.call_count, 6 + len(failures))
        self.assertEqual(set(status["cameras"]), set(CAMERA_IDS))
        for camera in CAMERA_IDS:
            row = status["cameras"][camera]
            self.assertEqual(row["capture_attempts"], burst["cameras"][camera]["capture_attempts"])
            self.assertEqual(row["ok"], camera not in failures)
            self.assertEqual(len(row["capture_attempts"]), 2 if camera in failures else 1)
        for camera in failures:
            failed = burst["cameras"][camera]
            self.assertNotIn("shots", failed)
            self.assertIn("private diagnostics suppressed", failed["error"])
        (self.frames / "vision.json").write_text(json.dumps({"capture_time_ct": now.isoformat(), "cameras": {}}))
        payload, _ = publish_github.payload(self.base)
        for camera in CAMERA_IDS:
            if camera in failures:
                self.assertIsNone(payload[camera + '.jpg'])
                self.assertNotIn('shots', burst['cameras'][camera])
            else:
                self.assertTrue(payload[camera + '.jpg'].startswith(b'\xff\xd8'))
        self.assertEqual(json.loads(payload["burst_status.json"]), burst)
        self.assert_private_absent(bc.STATUS_PATH.read_text() + bc.BURST_STATUS_PATH.read_text() + self.out.getvalue())
        self.assertEqual(self.sleep.call_args_list.count(unittest.mock.call(5)), 6)
        self.assertEqual(self.sleep.call_args_list.count(unittest.mock.call(8)), len(failures))

    def test_summaries_keep_timeouts_http_and_unknown_distinct(self):
        http = RuntimeError(SECRET)
        http.response = types.SimpleNamespace(status_code=429)
        for error, expected in (
            (subprocess.TimeoutExpired([SECRET], 60, stderr=SECRET), {"category": "capture_process_timeout"}),
            (http, {"category": "http_error", "http_status": 429}),
            (RuntimeError(SECRET), {"category": "unclassified_capture_failure"}),
            (subprocess.CalledProcessError(1, [SECRET], stderr=SECRET), {"category": "unclassified_ffmpeg_failure", "returncode": 1}),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(diagnostics.capture_failure_summary(error), expected)
        http.response.status_code = SECRET
        self.assertEqual(diagnostics.capture_failure_summary(http), {"category": "unclassified_capture_failure"})
        class BrokenError(Exception):
            @property
            def response(self):
                raise ValueError(SECRET)
        self.assertEqual(diagnostics.capture_failure_summary(BrokenError()), {"category": "unclassified_capture_failure"})


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))
import capture_diagnostics as diagnostics


class DiagnosticTests(unittest.TestCase):
    def test_local_diagnostics_are_not_in_public_payload(self):
        import publish_github
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            frames = base / "frames"
            frames.mkdir()
            doc = {"capture_time_ct": datetime.now(timezone.utc).isoformat(), "cameras": {}}
            for name in publish_github.METADATA:
                (frames / name).write_text(json.dumps(doc))
            for parent in (base, frames):
                (parent / "capture_diagnostics.jsonl").write_text("PRIVATE_DIAGNOSTIC")
            payload, _ = publish_github.payload(base)
            self.assertNotIn("capture_diagnostics.jsonl", payload)
            self.assertFalse(any(b"PRIVATE_DIAGNOSTIC" in value for value in payload.values() if value))

    def test_known_categories(self):
        for text, expected in (
            (b"RTSP/1.0 401 Unauthorized", "authorization_rejected"),
            ("403 Forbidden", "authorization_rejected"),
            ("404 Not Found", "stream_not_found"),
            ("Failed to resolve hostname", "dns_failure"),
            ("Connection refused", "connection_refused"),
            ("Connection timed out", "connection_timeout"),
            ("Connection reset by peer", "connection_reset"),
            ("TLS handshake failed", "tls_failure"),
            ("Invalid data found", "decoder_failure"),
            ("Output file is empty", "no_video"),
            (None, "unclassified_ffmpeg_failure"),
        ):
            with self.subTest(text=text):
                self.assertEqual(diagnostics.classify_stderr(text), expected)

    def test_secrets_and_untrusted_fields_never_written(self):
        secret = "rtsp://user:PASSWORD@private.example/video?token=SECRET"
        error = subprocess.CalledProcessError(1, ["ffmpeg", secret], stderr=secret + " 403 Forbidden")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostics.jsonl"
            with patch.object(diagnostics, "LOG_PATH", path):
                diagnostics.record_ffmpeg_failure(secret, secret, error)
            raw = path.read_text()
            self.assertNotIn("SECRET", raw)
            self.assertNotIn("PASSWORD", raw)
            self.assertNotIn("private.example", raw)
            record = json.loads(raw)
            self.assertEqual(record["camera_id"], "unknown")
            self.assertEqual(record["stage"], "unknown")
            self.assertEqual(record["category"], "authorization_rejected")
            self.assertEqual(record["returncode"], 1)

    def test_logging_failure_is_nonfatal(self):
        with patch.object(diagnostics, "LOG_PATH", Path("missing-parent/diagnostics.jsonl")):
            diagnostics.record_ffmpeg_failure("pcl_e2_back_deck", "live_rtsp", RuntimeError())

    def test_log_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostics.jsonl"
            with patch.object(diagnostics, "LOG_PATH", path), patch.object(diagnostics, "MAX_LOG_BYTES", 1):
                for _ in range(3):
                    diagnostics.record_ffmpeg_failure("pcl_e2_back_deck", "live_rtsp", RuntimeError())
            self.assertEqual(len(list(Path(directory).glob("*.jsonl"))), 2)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            self.assertEqual(len(path.with_suffix(".previous.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()

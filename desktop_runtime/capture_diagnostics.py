"""Local, allowlisted capture diagnostics: never retain stderr or stream URLs."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from camera_policy import CAMERA_IDS

LOG_PATH = Path(r"C:\JubileeCams\capture_diagnostics.jsonl")
MAX_LOG_BYTES = 256 * 1024


def classify_stderr(stderr):
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    text = str(stderr or "").lower()
    for category, markers in (
        ("authorization_rejected", ("401 unauthorized", "403 forbidden")),
        ("stream_not_found", ("404 not found",)),
        ("stream_unavailable", ("454 session not found", "503 service unavailable")),
        ("dns_failure", ("failed to resolve", "name or service not known", "getaddrinfo")),
        ("connection_refused", ("connection refused",)),
        ("connection_timeout", ("connection timed out", "operation timed out")),
        ("connection_reset", ("connection reset", "broken pipe")),
        ("tls_failure", ("tls handshake", "certificate verify failed")),
        ("decoder_failure", ("error while decoding", "invalid data found", "could not find codec parameters")),
        ("no_video", ("does not contain any stream", "output file is empty")),
    ):
        if any(marker in text for marker in markers):
            return category
    return "unclassified_ffmpeg_failure"


def capture_failure_summary(error):
    """Public-safe diagnostic codes, never exception text or command arguments.

    Categories describe observed errors, not proven root causes. Unknown errors
    remain unknown. Diagnostic extraction must not interfere with capture.
    """
    try:
        if isinstance(error, subprocess.TimeoutExpired):
            return {"category": "capture_process_timeout"}
        if isinstance(error, subprocess.CalledProcessError):
            code = error.returncode
            return {
                "category": classify_stderr(error.stderr),
                "returncode": code if type(code) is int else None,
            }
        response = getattr(error, "response", None)
        code = getattr(response, "status_code", None)
        if type(code) is int and 100 <= code <= 599:
            return {"category": "http_error", "http_status": code}
    except Exception:
        pass
    return {"category": "unclassified_capture_failure"}


def record_ffmpeg_failure(camera_id, stage, error):
    """Diagnostics must not change capture failure or retry behavior."""
    try:
        code = getattr(error, "returncode", None)
        record = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "camera_id": camera_id if camera_id in CAMERA_IDS else "unknown",
            "stage": stage if stage in {"burst_rtsp", "live_rtsp"} else "unknown",
            "category": classify_stderr(getattr(error, "stderr", None)),
            "returncode": code if type(code) is int else None,
        }
        # One current and one previous file bound local diagnostic storage.
        if LOG_PATH.exists() and LOG_PATH.stat().st_size >= MAX_LOG_BYTES:
            LOG_PATH.replace(LOG_PATH.with_suffix(".previous.jsonl"))
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        pass

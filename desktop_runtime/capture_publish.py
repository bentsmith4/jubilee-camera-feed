import subprocess
import socket
import sys
from pathlib import Path

BASE = Path(r"C:\JubileeCams")

# Shared across the hourly task and dawn runner. Task Scheduler's IgnoreNew
# policy only protects one task definition, so prevent cross-task overlap here.
lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock.bind(("127.0.0.1", 47652))
except OSError:
    print("Jubilee canonical pipeline is already running; this cycle yields.")
    sys.exit(0)

steps = [
    (
        "3-FRAME BURST CAPTURE",
        BASE / "burst_capture.py",
        ["--force"]
    ),
    (
        "3-FRAME VISION ANALYSIS",
        BASE / "analyze_frames.py",
        []
    ),
    (
        "HIGH-PRIORITY ALLIGATOR ALERT CHECK",
        BASE / "notify_alligator.py",
        []
    ),
    (
        "R2 LATEST + BURST ARCHIVE",
        BASE / "upload_frames.py",
        []
    ),
    (
        "PRIVATE SHORELINE LOCAL ARCHIVE",
        BASE / "private_capture.py",
        []
    ),
    (
        "GITHUB LATEST MIRROR",
        BASE / "publish_github.py",
        []
    ),
]

for label, script, args in steps:
    print()
    print("=" * 70)
    print(label)
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, str(script), *args]
    )

    if result.returncode != 0:
        raise SystemExit(
            f"{label} FAILED with exit code {result.returncode}"
        )

print()
print("=" * 70)
print("FULL JUBILEE BURST + VISION PIPELINE SUCCESS")
print("=" * 70)

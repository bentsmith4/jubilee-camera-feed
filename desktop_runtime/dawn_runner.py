import argparse
import ctypes
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sun

from capture_service import (
    adaptive_active,
    latest_capture_time,
    read_vision,
    slot as cadence_slot,
    spacing_remaining,
)

BASE = Path(r"C:\JubileeCams")
REFRESH = BASE / "capture_publish.py"
LOG = BASE / "dawn_runner.log"

TZ = ZoneInfo("America/Chicago")

OBSERVER = Observer(latitude=30.6035, longitude=-87.9036, elevation=0)
INTERVAL = timedelta(minutes=20)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(enable=True):
    if enable:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
    else:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def log(msg):
    now = datetime.now(TZ)
    line = f"{now:%Y-%m-%d %H:%M:%S %Z}  {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def todays_schedule():
    now = datetime.now(TZ)
    solar = sun(OBSERVER, date=now.date(), tzinfo=TZ)
    dawn = solar["dawn"]
    start = dawn - timedelta(hours=2)
    end = dawn + timedelta(hours=2)
    slots = []
    t = start
    while t <= end:
        slots.append(t)
        t += INTERVAL
    return now, dawn, start, end, slots


def wait_until(target):
    while True:
        now = datetime.now(TZ)
        seconds = (target - now).total_seconds()
        if seconds <= 0:
            return
        time.sleep(min(seconds, 30))


def capture():
    result = subprocess.run(
        [sys.executable, str(REFRESH), "--force"],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log("  " + line)
    if result.stderr:
        log("Diagnostic stderr suppressed; inspect local step health")
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now, dawn, start, end, slots = todays_schedule()
    log(f"Civil dawn: {dawn:%I:%M:%S %p}")
    log(f"Capture window: {start:%I:%M:%S %p} - {end:%I:%M:%S %p}")
    log(f"Scheduled capture cycles: {len(slots)}")

    if args.dry_run:
        for i, scheduled in enumerate(slots, 1):
            log(f"{i:02d}: {scheduled:%I:%M:%S %p}")
        return

    if datetime.now(TZ) > end:
        log("Today's dawn capture window has already ended.")
        return

    keep_awake(True)
    try:
        log("Dawn camera runner active.")
        last_due = None
        while True:
            now = datetime.now(TZ)
            if now < start:
                wait_until(start)
                continue
            if now > end:
                break

            adaptive = adaptive_active(now, dawn, start, end, read_vision())
            due = cadence_slot(now, start, end, adaptive=adaptive)

            if due is not None and due != last_due:
                try:
                    remaining = spacing_remaining(now, latest_capture_time())
                except (OSError, ValueError):
                    log("Canonical spacing state invalid; capture withheld.")
                    return

                if remaining > timedelta(0):
                    wait_until(now + remaining)
                    continue

                mode = "adaptive 15-minute" if adaptive else "normal 20-minute"
                log(f"Capture for {due} ({mode})")
                rc = capture()
                last_due = due
                if rc == 0:
                    log("Capture cycle completed.")
                else:
                    log(f"Capture cycle returned code {rc}.")

            time.sleep(5)

        log("Dawn camera sequence complete.")
    finally:
        keep_awake(False)


if __name__ == "__main__":
    main()

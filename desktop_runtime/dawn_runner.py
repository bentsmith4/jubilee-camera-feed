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

BASE = Path(r"C:\JubileeCams")
REFRESH = BASE / "capture_publish.py"
LOG = BASE / "dawn_runner.log"

TZ = ZoneInfo("America/Chicago")

# Daphne/Montrose reference point.
OBSERVER = Observer(
    latitude=30.6035,
    longitude=-87.9036,
    elevation=0
)

INTERVAL = timedelta(minutes=20)

# Prevent Windows from sleeping while the dawn sequence is running.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(enable=True):
    if enable:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
    else:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS
        )


def log(msg):
    now = datetime.now(TZ)
    line = f"{now:%Y-%m-%d %H:%M:%S %Z}  {msg}"
    print(line)

    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def todays_schedule():
    now = datetime.now(TZ)

    solar = sun(
        OBSERVER,
        date=now.date(),
        tzinfo=TZ
    )

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
        [
            sys.executable,
            str(REFRESH),
            "--force"
        ],
        capture_output=True,
        text=True,
        timeout=900
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
        for i, slot in enumerate(slots, 1):
            log(f"{i:02d}: {slot:%I:%M:%S %p}")
        return

    # If Windows started the task late, don't recreate old captures.
    remaining = [x for x in slots if x >= datetime.now(TZ)]

    if not remaining:
        log("Today's dawn capture window has already ended.")
        return

    keep_awake(True)

    try:
        log("Dawn camera runner active.")

        for index, slot in enumerate(remaining, 1):
            wait_until(slot)

            log(
                f"Capture {index}/{len(remaining)} "
                f"for nominal slot {slot:%I:%M:%S %p}"
            )

            rc = capture()

            if rc == 0:
                log("Capture cycle completed.")
            else:
                log(f"Capture cycle returned code {rc}.")

        log("Dawn camera sequence complete.")

    finally:
        keep_awake(False)


if __name__ == "__main__":
    main()


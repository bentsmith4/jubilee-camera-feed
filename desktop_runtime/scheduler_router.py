"""Route the credentialed Windows fallback task using coordinator cadence policy."""

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from seasonal_policy import require_season

import refresh_all as ra
from capture_service import latest_capture_time, slot, spacing_remaining

BASE = Path(r"C:\JubileeCams")


def main():
    require_season()
    now, _dawn, start, end = ra.dawn_window()

    # Preserve the legacy bootstrap into the dawn runner. The active production
    # task is the single capture_service coordinator; this path remains a
    # guarded fallback and must not create a second Windows task.
    use_dawn_runner = now.hour == 3 or start <= now <= end

    if use_dawn_runner:
        script = BASE / "dawn_runner.py"
        mode = "dawn_coordinator"
    else:
        due = slot(now, start, end, adaptive=False)
        if due is None:
            print("Jubilee scheduler mode: reduced_overnight_or_handoff_hold")
            return

        try:
            remaining = spacing_remaining(now, latest_capture_time())
        except (OSError, ValueError):
            print("Jubilee scheduler mode: spacing_state_invalid; capture withheld")
            return

        if remaining > timedelta(0):
            print(
                "Jubilee scheduler mode: global_spacing_hold; "
                f"remaining_seconds={int(remaining.total_seconds())}"
            )
            return

        script = BASE / "capture_publish.py"
        mode = "baseline_guarded"

    print(f"Jubilee scheduler mode: {mode}; script={script}")

    result = subprocess.run([sys.executable, str(script)], cwd=BASE)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

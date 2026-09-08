"""Route the single credentialed Windows task to hourly or dawn cadence."""

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from seasonal_policy import require_season

import refresh_all as ra

BASE = Path(r"C:\JubileeCams")


def main():
    require_season()
    now, _dawn, start, end = ra.dawn_window()

    # The task fires at :06. Starting the dawn runner during the 3 AM firing
    # lets it wait for the seasonally computed first slot. StartWhenAvailable
    # is also covered if Windows resumes after the window has begun.
    use_dawn_runner = now.hour == 3 or start <= now <= end
    script = BASE / ("dawn_runner.py" if use_dawn_runner else "capture_publish.py")

    mode = "dawn_20_minute" if use_dawn_runner else "hourly_baseline"
    print(f"Jubilee scheduler mode: {mode}; script={script}")

    result = subprocess.run([sys.executable, str(script)], cwd=BASE)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

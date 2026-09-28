"""One bounded acquisition queue, distinct live and canonical products."""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import refresh_all as ra
from seasonal_policy import in_season

BASE = Path(r"C:\JubileeCams")
STATE = BASE / "capture_service_state.json"
LOG = BASE / "capture_service.log"
VISION = BASE / "frames" / "vision.json"

MIN_CANONICAL_SPACING = timedelta(minutes=15)
VISION_MAX_AGE = timedelta(minutes=60)
OVERNIGHT_BASELINE_HOURS = {0, 2, 4, 20, 22}


def slot(now, start, end):
    """Return the current regular canonical slot, or None during thinned hours."""
    if start <= now <= end:
        return "dawn:" + start.date().isoformat() + ":" + str(
            int((now - start).total_seconds() // 1200)
        )

    hour = now.replace(minute=6, second=0, microsecond=0)
    if now < hour:
        hour -= timedelta(hours=1)

    # From 20:00 through 04:59, retain only alternating :06 baselines.
    # This cuts the overnight full camera/vision load roughly in half while
    # preserving the fixed 20-minute civil-dawn +/-2-hour schedule below.
    if (hour.hour >= 20 or hour.hour <= 4) and hour.hour not in OVERNIGHT_BASELINE_HOURS:
        return None

    return "hour:" + hour.isoformat()


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def last_success_time(state):
    return _parse_time(state.get("last_canonical_success"))


def spacing_ready(now, state):
    """Enforce one global floor across baseline, dawn and adaptive captures."""
    last = last_success_time(state)
    return last is None or now >= last + MIN_CANONICAL_SPACING


def strong_activity_evidence(vision, now):
    """Use only fresh, explicit pre-dawn activity evidence to accelerate cadence."""
    if not isinstance(vision, dict):
        return False

    captured = _parse_time(vision.get("capture_time_ct"))
    if captured is None:
        return False
    age = now - captured
    if age < timedelta(minutes=-5) or age > VISION_MAX_AGE:
        return False

    cross = vision.get("cross_camera", {})
    for field in (
        "overall_visual_jubilee_signal",
        "montrose_visual_signal",
        "point_clear_visual_signal",
    ):
        if cross.get(field) in {"moderate", "strong"}:
            return True

    cameras = vision.get("cameras", {})
    if not isinstance(cameras, dict):
        return False

    for camera in cameras.values():
        if not isinstance(camera, dict) or camera.get("status") != "ok":
            continue
        if camera.get("temporal_jubilee_signal") in {"moderate", "strong"}:
            return True
        if camera.get("overall_jubilee_visual_signal") in {"moderate", "strong"}:
            return True
        if camera.get("flashlight_activity") == "clear":
            return True
        if camera.get("clustered_search_behavior") == "clear":
            return True
        if camera.get("people_collecting_seafood") == "clear":
            return True

        score = camera.get("human_sensor_score")
        detectable = camera.get("human_sensor_detectability") not in {"poor", "unknown"}
        if (
            type(score) in (int, float)
            and score >= 0.5
            and detectable
            and camera.get("motion_pattern") == "searching"
        ):
            return True

    return False


def load_activity_evidence(now):
    try:
        return strong_activity_evidence(json.loads(VISION.read_text()), now)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def last_regular_slot(state):
    current = state.get("last_regular_slot")
    if isinstance(current, str):
        return current
    legacy = state.get("canonical_slot")
    if isinstance(legacy, str) and legacy.startswith(("hour:", "dawn:")):
        return legacy
    return None


def pending_capture(now, dawn, start, end, state, activity=False):
    """Choose one regular or adaptive capture without creating a second owner."""
    regular = slot(now, start, end)
    if regular is not None and regular != last_regular_slot(state):
        return regular

    # Adaptive acceleration is intentionally pre-dawn only. The normal dawn
    # schedule remains anchored at 20-minute slots; activity may add a capture
    # between completed regular slots, but never inside the 15-minute floor.
    if (
        start <= now < dawn
        and activity
        and spacing_ready(now, state)
        and last_success_time(state) is not None
    ):
        return "adaptive:" + last_success_time(state).isoformat()

    return None


def log(message):
    with LOG.open("a", encoding="utf-8") as out:
        out.write(datetime.now(ra.TZ).isoformat() + " " + message + "\n")


def execute(script, limit):
    process = subprocess.Popen(
        [sys.executable, str(BASE / script)],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, _stderr = process.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
        )
        process.communicate()
        log(script + " timeout; child process tree stopped")
        return False

    # Log only allowlisted completion summaries, not child exceptions or URLs.
    for line in stdout.splitlines():
        if line.startswith(
            (
                "GITHUB APPEND-ONLY PUBLISH SUCCESS:",
                "PRIVATE SHORELINE:",
                "FULL JUBILEE BURST",
                "Fresh cameras published:",
            )
        ):
            log(line)
    log(script + " exit=" + str(process.returncode))
    return process.returncode == 0


def main():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47651))
    except OSError:
        return

    try:
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        if not isinstance(state, dict):
            raise ValueError("state is not an object")
    except (OSError, UnicodeError, ValueError):
        # Preserve the deployed recovery behavior after an interrupted state write.
        state = {}
        log("Coordinator state unreadable; rebuilding from fresh captures")
    if "last_regular_slot" not in state:
        migrated = last_regular_slot(state)
        if migrated is not None:
            state["last_regular_slot"] = migrated

    next_live = 0
    retry_at = 0
    failures = 0
    log("Coordinated capture service started")

    while True:
        now, dawn, start, end = ra.dawn_window()
        active = in_season(now)
        activity = active and start <= now < dawn and load_activity_evidence(now)
        due = pending_capture(now, dawn, start, end, state, activity=activity)

        state["canonical_monitoring_status"] = (
            "scheduled" if active else "offseason_not_monitored"
        )

        if (
            active
            and due is not None
            and spacing_ready(now, state)
            and time.monotonic() >= retry_at
        ):
            if due.startswith("adaptive:"):
                log("Adaptive pre-dawn activity evidence requested canonical capture")

            if execute("capture_publish.py", 900):
                if due.startswith(("hour:", "dawn:")):
                    state["last_regular_slot"] = due
                state["canonical_slot"] = due
                completed = datetime.now(ra.TZ)
                if in_season(completed):
                    state["last_canonical_success"] = completed.isoformat()
                    state["canonical_monitoring_status"] = "completed"
                else:
                    state["canonical_monitoring_status"] = "offseason_not_monitored"
                failures = 0
            else:
                failures += 1
                retry_at = time.monotonic() + min(900, 60 * 2 ** min(failures, 4))
                state["canonical_failures"] = failures
                log("Canonical failure; bounded backoff applied")

        if time.monotonic() >= next_live:
            if execute("live_capture.py", 300):
                if execute("live_upload.py", 90):
                    state["last_live_success"] = datetime.now(ra.TZ).isoformat()
            next_live = time.monotonic() + 180

        state["heartbeat"] = datetime.now(ra.TZ).isoformat()
        tmp = STATE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as out:
            out.write(json.dumps(state, indent=2))
            out.flush()
            os.fsync(out.fileno())
        tmp.replace(STATE)
        time.sleep(5)


if __name__ == "__main__":
    main()

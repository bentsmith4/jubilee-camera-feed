"""One bounded acquisition queue, distinct live and canonical products."""
import json
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
FRAMES = BASE / "frames"
BURST_STATUS = FRAMES / "burst_status.json"
VISION = FRAMES / "vision.json"

MIN_CANONICAL_SPACING = timedelta(minutes=15)
NORMAL_DAWN_INTERVAL = timedelta(minutes=20)
ADAPTIVE_DAWN_INTERVAL = timedelta(minutes=15)

STRONG_JUBILEE_SIGNALS = {"moderate", "strong"}
STRONG_BIOLOGICAL_VALUES = {
    "clear_abnormal",
    "dense",
    "clear",
    "widespread",
    "multiple",
}
STRONG_BIOLOGICAL_FIELDS = {
    "fish_surface_activity",
    "fish_gulping_or_smoking",
    "shrimp_surface_popping",
    "shrimp_surface_concentration",
    "crab_surface_swimming",
    "crab_climbing_structure",
    "flounder_or_flatfish_shallow",
    "eel_displacement",
    "stingray_or_other_bottom_fauna_displacement",
    "shoreline_or_structure_accumulation",
    "offshore_bottom_fauna_surface_aggregation",
    "animal_lethargy_or_abnormal_motion",
}


def _baseline_hour(now):
    hour = now.replace(minute=6, second=0, microsecond=0)
    if now < hour:
        hour -= timedelta(hours=1)
    return hour


def _reduced_overnight(hour):
    return hour.hour >= 20 or hour.hour <= 4


def _overnight_baseline_allowed(hour):
    if not _reduced_overnight(hour):
        return True
    return hour.hour % 2 == 0


def slot(now, start, end, adaptive=False):
    """Return the one canonical due-key for this instant, or None when suppressed."""
    if start <= now <= end:
        interval = ADAPTIVE_DAWN_INTERVAL if adaptive else NORMAL_DAWN_INTERVAL
        index = int((now - start).total_seconds() // interval.total_seconds())
        prefix = "dawn-adaptive" if adaptive else "dawn"
        return f"{prefix}:{start.date().isoformat()}:{index}"

    hour = _baseline_hour(now)
    if not _overnight_baseline_allowed(hour):
        return None

    # Do not fire the last baseline when the first dawn slot is less than the
    # global spacing floor away. This preserves the dawn handoff instead.
    if hour <= now < start:
        gap = start - hour
        if timedelta(0) <= gap < MIN_CANONICAL_SPACING:
            return None

    return "hour:" + hour.isoformat()


def _as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def strong_activity_evidence(vision):
    """Return True only for explicit, higher-confidence pre-dawn activity."""
    if not isinstance(vision, dict):
        return False

    cross = vision.get("cross_camera")
    if isinstance(cross, dict):
        if cross.get("overall_visual_jubilee_signal") in STRONG_JUBILEE_SIGNALS:
            return True
        if cross.get("temporal_confirmation") in {"moderate", "strong", "clear"}:
            return True

    cameras = vision.get("cameras")
    if not isinstance(cameras, dict):
        return False

    for camera in cameras.values():
        if not isinstance(camera, dict) or camera.get("status") == "failed":
            continue

        if camera.get("overall_jubilee_visual_signal") in STRONG_JUBILEE_SIGNALS:
            return True
        if camera.get("temporal_jubilee_signal") in STRONG_JUBILEE_SIGNALS:
            return True

        confidence = _as_number(camera.get("confidence"))
        detectability = camera.get("human_sensor_detectability")
        human_usable = confidence is not None and confidence >= 0.70 and detectability not in {
            "poor",
            "unknown",
        }

        if human_usable and camera.get("flashlight_activity") == "clear":
            return True
        if human_usable and camera.get("clustered_search_behavior") == "clear":
            return True
        if human_usable and camera.get("people_collecting_seafood") == "clear":
            return True

        human_score = _as_number(camera.get("human_sensor_score"))
        human_confidence = _as_number(camera.get("human_sensor_confidence"))
        if (
            human_score is not None
            and human_score >= 0.5
            and human_confidence is not None
            and human_confidence >= 0.70
            and detectability not in {"poor", "unknown"}
        ):
            return True

        if confidence is not None and confidence >= 0.70:
            for field in STRONG_BIOLOGICAL_FIELDS:
                if camera.get(field) in STRONG_BIOLOGICAL_VALUES:
                    return True

    return False


def read_vision(path=VISION):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def adaptive_active(now, dawn, start, end, vision):
    return (
        start <= now < dawn
        and now <= end
        and strong_activity_evidence(vision)
    )


def latest_capture_time(path=BURST_STATUS):
    """Read the canonical burst timestamp strictly; malformed state is an error."""
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("burst status is not a JSON object")

    raw = data.get("capture_time_ct")
    if not isinstance(raw, str):
        raise ValueError("burst status capture_time_ct is missing or not a string")

    captured = datetime.fromisoformat(raw)
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("burst status capture_time_ct must be timezone-aware")
    return captured


def spacing_remaining(now, last_capture):
    if last_capture is None:
        return timedelta(0)
    elapsed = now - last_capture
    if elapsed < timedelta(0):
        raise ValueError("latest capture timestamp is in the future")
    return max(timedelta(0), MIN_CANONICAL_SPACING - elapsed)


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

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    next_live = 0
    retry_at = 0
    failures = 0
    log("Coordinated capture service started")

    while True:
        now, dawn, start, end = ra.dawn_window()
        vision = read_vision()
        adaptive = adaptive_active(now, dawn, start, end, vision)
        due = slot(now, start, end, adaptive=adaptive)
        active = in_season(now)

        if not active:
            state["canonical_monitoring_status"] = "offseason_not_monitored"
        elif due is None:
            state["canonical_monitoring_status"] = "reduced_overnight_wait"
        else:
            state["canonical_monitoring_status"] = "scheduled"

        state["canonical_cadence"] = (
            "adaptive_15_minute"
            if adaptive
            else "dawn_20_minute"
            if start <= now <= end
            else "reduced_overnight"
            if _reduced_overnight(_baseline_hour(now))
            else "hourly_baseline"
        )

        if (
            active
            and due is not None
            and state.get("canonical_slot") != due
            and time.monotonic() >= retry_at
        ):
            try:
                remaining = spacing_remaining(now, latest_capture_time())
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                state["canonical_monitoring_status"] = "spacing_state_invalid"
                state["canonical_spacing_error"] = type(exc).__name__
                log("Canonical spacing state invalid; capture withheld")
            else:
                state.pop("canonical_spacing_error", None)
                if remaining > timedelta(0):
                    state["canonical_monitoring_status"] = "spacing_hold"
                    state["canonical_spacing_remaining_seconds"] = int(
                        remaining.total_seconds()
                    )
                else:
                    state.pop("canonical_spacing_remaining_seconds", None)
                    state["last_canonical_dispatch"] = now.isoformat()

                    if execute("capture_publish.py", 900):
                        state["canonical_slot"] = due
                        if in_season(datetime.now(ra.TZ)):
                            state["last_canonical_success"] = datetime.now(
                                ra.TZ
                            ).isoformat()
                            state["canonical_monitoring_status"] = "completed"
                        else:
                            state[
                                "canonical_monitoring_status"
                            ] = "offseason_not_monitored"
                        failures = 0
                    else:
                        failures += 1
                        retry_at = time.monotonic() + min(
                            900, 60 * 2 ** min(failures, 4)
                        )
                        state["canonical_failures"] = failures
                        log("Canonical failure; bounded backoff applied")

        if time.monotonic() >= next_live:
            if execute("live_capture.py", 300):
                if execute("live_upload.py", 90):
                    state["last_live_success"] = datetime.now(ra.TZ).isoformat()
            next_live = time.monotonic() + 180

        state["heartbeat"] = datetime.now(ra.TZ).isoformat()
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(STATE)
        time.sleep(5)


if __name__ == "__main__":
    main()

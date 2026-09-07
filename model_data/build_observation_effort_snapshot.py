#!/usr/bin/env python3
"""Build leakage-safe prospective observation-effort records.

This records what could actually have been seen during a sensing cycle. It does
not turn absence of a report into a Jubilee negative. A clean observed control
is only possible where camera geometry and detectability are sufficient for the
specific visible scope.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
OUT = HERE / "observation_effort_snapshot.json"
LEDGER = HERE / "observation_effort_ledger.jsonl"

CELL_CAMERAS = {
    "Montrose": ["montrose_shoreline", "montrose_pier_boat", "montrose_pier_bird"],
    "Point Clear/Grand Hotel": ["pcl_e2_back_deck", "pcl_e2_bay_mouth", "pcl_e3_bay_mouth"],
}

PRIMARY_CONTACT_CAMERA = {
    "Montrose": "montrose_shoreline",
    # No Point Clear owner camera is a close swash-zone/shoreline camera.
    "Point Clear/Grand Hotel": None,
}


def load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except ValueError:
        return None


def in_window(t, start, end):
    return bool(t and start and end and start <= t <= end)


def no_visual_event_evidence(v):
    return v.get("overall_jubilee_visual_signal") in ("none", "none_visible") and v.get("temporal_jubilee_signal") in ("none", "none_visible")


def sufficient_contact_detectability(v):
    return (
        v.get("visibility") in ("good", "fair")
        and v.get("detectability") in ("high", "moderate")
        and v.get("status") == "ok"
    )


def camera_integrity(camera_id, status, burst, vision, root, now):
    s = status.get("cameras", {}).get(camera_id, {})
    b = burst.get("cameras", {}).get(camera_id, {})
    v = vision.get("cameras", {}).get(camera_id, {})
    issues = []
    captures = [parse_dt(d.get("capture_time_ct")) for d in (status, burst, vision)]
    if not all(captures) or len(set(captures)) != 1:
        issues.append("CAPTURE_BURST_VISION_MISMATCH")
    if captures[0] is None or not -5 <= (now - captures[0]).total_seconds() <= 3600:
        issues.append("STALE_FUTURE_OR_UNTIMED_CAPTURE")
    t = parse_dt(s.get("timestamp_ct"))
    if t is None or not -5 <= (now-t).total_seconds() <= 3600:
        issues.append("STALE_FUTURE_OR_UNTIMED_CAMERA")
    shots = b.get("shots", [])
    times = [parse_dt(x.get("timestamp_ct")) for x in shots]
    vtimes = [parse_dt(x.get("timestamp_ct")) for x in v.get("burst_shots", [])]
    if not (s.get("ok") is True and b.get("ok") is True and v.get("status") == "ok"
            and len(times) == 3 and all(times) and times == vtimes
            and all(5 <= (times[i+1]-times[i]).total_seconds() <= 30 for i in (0,1))
            and times[-1] == t and v.get("burst_frame_count") == 3):
        issues.append("INVALID_TEMPORAL_BURST_OR_VISION")
    image = root / (camera_id + ".jpg")
    raw = image.read_bytes() if image.is_file() else b""
    if not raw or len(raw) != s.get("bytes") or not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9"):
        issues.append("LATEST_IMAGE_INTEGRITY_FAILED")
    return issues, hashlib.sha256(raw).hexdigest() if raw else None


def build(now=None):
    now = now or datetime.now(timezone.utc)
    status = load_json(ROOT / "status.json")
    vision = load_json(ROOT / "vision.json")
    burst = load_json(ROOT / "burst_status.json")
    public_log = load_json(HERE / "public_camera_observation_log.json", {"records": []})

    capture = parse_dt(status.get("capture_time_ct") or vision.get("capture_time_ct"))
    window_start = parse_dt(status.get("window_start_ct") or vision.get("window_start_ct"))
    window_end = parse_dt(status.get("window_end_ct") or vision.get("window_end_ct"))
    cycle_in_target_window = in_window(capture, window_start, window_end)

    output = {
        "schema_version": "1.2",
        "evaluated_at_utc": now.isoformat(),
        "input_hashes": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ("status.json", "burst_status.json", "vision.json") if (ROOT/name).exists()},
        "assessment_basis": "validated_upstream_three_frame_vision_not_independent_pixel_review",
        "clean_training_negative_count": 0,
        "generated_from_capture_time_ct": status.get("capture_time_ct") or vision.get("capture_time_ct"),
        "target_window_start_ct": status.get("window_start_ct") or vision.get("window_start_ct"),
        "target_window_end_ct": status.get("window_end_ct") or vision.get("window_end_ct"),
        "cycle_in_target_predawn_dawn_window": cycle_in_target_window,
        "cells": [],
        "production_action": "NO_CHANGE",
        "guardrails": [
            "This file records observation effort and detectability, not Jubilee probability.",
            "No-report is never promoted to an observed non-event.",
            "Dark, stale, frozen, obstructed or low-detectability views are UNKNOWN.",
            "A camera negative applies only to the geometry actually visible in that frame.",
            "Point Clear owner cameras do not provide a close swash-zone negative; private cameras alone cannot create a full-cell Point Clear control.",
        ],
    }

    status_cams = status.get("cameras", {})
    vision_cams = vision.get("cameras", {})

    for cell, camera_ids in CELL_CAMERAS.items():
        camera_rows = []
        for camera_id in camera_ids:
            s = status_cams.get(camera_id, {})
            v = vision_cams.get(camera_id, {})
            issues, image_hash = camera_integrity(camera_id, status, burst, vision, ROOT, now)
            camera_rows.append({
                "integrity_issues": issues,
                "latest_image_sha256": image_hash,
                "camera_id": camera_id,
                "capture_ok": not issues,
                "visibility": v.get("visibility", "unknown"),
                "detectability": v.get("detectability", "unknown"),
                "overall_visual_signal": v.get("overall_jubilee_visual_signal", "unknown"),
                "human_sensor_detectability": v.get("human_sensor_detectability", "unknown"),
                "flashlight_activity": v.get("flashlight_activity", "unknown"),
                "people_present": v.get("people_present", "unknown"),
            })

        primary_id = PRIMARY_CONTACT_CAMERA[cell]
        primary = vision_cams.get(primary_id, {}) if primary_id else {}
        primary_row = next((r for r in camera_rows if r["camera_id"] == primary_id), {})
        primary_ok = bool(primary_id and primary_row.get("capture_ok") and sufficient_contact_detectability(primary))
        primary_no_event = bool(primary_ok and no_visual_event_evidence(primary))

        if not cycle_in_target_window:
            eligibility = "NOT_ELIGIBLE_OUTSIDE_TARGET_WINDOW"
            strength = "none"
        elif primary_no_event:
            eligibility = "CANDIDATE_VISIBLE_SCOPE_CONTROL"
            strength = "moderate"
        elif primary_id and not primary_ok:
            eligibility = "UNKNOWN_PRIMARY_CONTACT_VIEW_INADEQUATE"
            strength = "none"
        else:
            eligibility = "PARTIAL_OBSERVABILITY_NOT_CLEAN_CELL_CONTROL"
            strength = "none"

        output["cells"].append({
            "shoreline_cell": cell,
            "independent_private_site_group": "montrose_owner_cluster" if cell == "Montrose" else "point_clear_landing_owner_cluster",
            "private_camera_expected_count": len(camera_ids),
            "private_camera_fresh_or_ok_count": sum(r["capture_ok"] for r in camera_rows),
            "primary_contact_camera": primary_id,
            "camera_rows": camera_rows,
            "control_eligibility": eligibility,
            "negative_evidence_strength": strength,
            "scope_note": (
                "If eligible, negative evidence is restricted to the 437 waterline/beach segments visible in montrose_shoreline."
                if cell == "Montrose" else
                "Point Clear private cameras provide marina/Bay context but no close beach waterline; retain as observation effort only."
            ),
        })

    records = public_log.get("records", []) if isinstance(public_log, dict) else []
    output["public_camera_structured_records_available"] = len(records)
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def append_if_target_window(output, ledger_path=LEDGER):
    """Append exactly one record per capture identity, and only for dawn-window cycles."""
    capture_id = output.get("generated_from_capture_time_ct")
    if not output.get("cycle_in_target_predawn_dawn_window") or not capture_id:
        return {"appended": False, "reason": "outside_target_window_or_missing_capture_id"}
    existing_ids = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing_ids.add(json.loads(line).get("generated_from_capture_time_ct"))
            except json.JSONDecodeError:
                raise ValueError("observation effort ledger contains invalid JSONL")
    if capture_id in existing_ids:
        return {"appended": False, "reason": "duplicate_capture_id"}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(output, separators=(",", ":"), sort_keys=True) + "\n")
    return {"appended": True, "reason": "new_target_window_capture"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--append-ledger", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    globals()["ROOT"] = args.root
    globals()["OUT"] = args.out
    args.out.parent.mkdir(parents=True, exist_ok=True)
    output = build()
    result = {"snapshot": output}
    if args.append_ledger:
        result["ledger"] = append_if_target_window(output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a leakage-safe prospective observation-effort snapshot.

This records what could actually have been seen during a sensing cycle. It does
not turn absence of a report into a Jubilee negative. A clean observed control
is only possible where the camera geometry and detectability are sufficient for
the specific visible scope.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "observation_effort_snapshot.json"

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
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
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


def build():
    status = load_json(ROOT / "status.json")
    vision = load_json(ROOT / "vision.json")
    public_log = load_json(Path(__file__).resolve().parent / "public_camera_observation_log.json", {"records": []})

    capture = parse_dt(status.get("capture_time_ct") or vision.get("capture_time_ct"))
    window_start = parse_dt(status.get("window_start_ct") or vision.get("window_start_ct"))
    window_end = parse_dt(status.get("window_end_ct") or vision.get("window_end_ct"))
    cycle_in_target_window = in_window(capture, window_start, window_end)

    output = {
        "schema_version": "1.0",
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
            camera_rows.append({
                "camera_id": camera_id,
                "capture_ok": bool(s.get("ok")) and v.get("status") == "ok",
                "visibility": v.get("visibility", "unknown"),
                "detectability": v.get("detectability", "unknown"),
                "overall_visual_signal": v.get("overall_jubilee_visual_signal", "unknown"),
                "human_sensor_detectability": v.get("human_sensor_detectability", "unknown"),
                "flashlight_activity": v.get("flashlight_activity", "unknown"),
                "people_present": v.get("people_present", "unknown"),
            })

        primary_id = PRIMARY_CONTACT_CAMERA[cell]
        primary = vision_cams.get(primary_id, {}) if primary_id else {}
        primary_ok = bool(primary_id and status_cams.get(primary_id, {}).get("ok") and sufficient_contact_detectability(primary))
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
            strength = "weak"

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


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

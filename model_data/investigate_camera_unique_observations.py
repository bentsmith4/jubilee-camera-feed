#!/usr/bin/env python3
"""Extract PR76 cases without changing its scorer or making network/model calls.

Run from repository root. Output contains structured evidence and existing image
hashes only; it does not copy media. Manual interpretation is in the companion MD.
"""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from analyze_camera_marginal_value import (
    CAMERAS, SITE, SIGNAL_FIELDS, POSITIVE_VALUES, normalized, observation_state,
)

SOURCE_HEAD = "519d5bfdc5abe64fb5eb1fa7da009531c9467e64"
RESEARCH_HEAD = "c73cf645e43c8e30fc34574f9d8c957098a16c3a"
OUTCOME_HEAD = "9f32b0494c70b63778c4ffca2efa975c7e8137a0"


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)


def read(ref, path):
    return git("show", f"{ref}:{path}")


def provenance(ref, path):
    raw = read(ref, path)
    return {"commit_sha": ref, "path": path,
            "blob_sha": git("rev-parse", f"{ref}:{path}").decode().strip(),
            "sha256": hashlib.sha256(raw).hexdigest()}


def index_observations():
    index = {}
    paths = git("ls-tree", "-r", "--name-only", OUTCOME_HEAD,
                "model_data/observation_records").decode().splitlines()
    for path in paths:
        obj = json.loads(read(OUTCOME_HEAD, path))
        t = obj.get("generated_from_capture_time_ct")
        index.setdefault(t, []).append((path, obj))
    return index


def relevant_analysis(row):
    # Preserve every scored field plus context, not unrelated alligator records.
    return {k: v for k, v in row.items() if k in SIGNAL_FIELDS or k in (
        "status", "visibility", "detectability", "water_surface",
        "rain_surface_interference", "wake_interference", "artificial_light_confounding",
        "motion_pattern", "temporal_persistence", "human_sensor_score",
        "human_sensor_confidence", "human_sensor_detectability", "confidence",
        "activity_changed_across_frames", "likely_temporal_artifact", "burst_shots",
        "burst_frame_count", "frame_1_summary", "frame_2_summary", "frame_3_summary",
        "temporal_summary")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    scorer_path = "model_data/analyze_camera_marginal_value.py"
    assert Path(scorer_path).read_bytes() == read(RESEARCH_HEAD, scorer_path), \
        "Use the unchanged PR76 scorer at the pinned research head."
    commits = git("log", SOURCE_HEAD, "--format=%H", "--", "vision.json").decode().splitlines()
    snapshots = []
    for sha in commits:
        raw = read(sha, "vision.json")  # fail closed on any missing/corrupt source
        snapshots.append((sha, json.loads(raw)))
    snapshots.sort(key=lambda pair: (pair[1]["capture_time_ct"], pair[0]))
    index = index_observations()
    evidence_paths = ["model_data/event_history.json",
                      "model_data/private_camera_signal_contracts.json",
                      "model_data/owner_reports/2026-09-12-eastern-shore-non-event.json",
                      "model_data/owner_reports/2026-09-09-marina-unknown.json",
                      "model_data/j10_montrose_control_verification_20260930.json",
                      "model_data/j10_matched_control_sensitivity_20261010.json",
                      "model_data/public_camera_observation_log.json"]
    events = json.loads(read(OUTCOME_HEAD, evidence_paths[0]))["events"]
    positives, uniques = [], []
    for sha, snap in snapshots:
        states = {c: observation_state(snap["cameras"].get(c)) for c in CAMERAS}
        for camera in CAMERAS:
            if states[camera] != "POSITIVE":
                continue
            row = snap["cameras"][camera]
            peers = {p: states[p] for p in CAMERAS if p != camera and SITE[p] == SITE[camera]}
            unique = all(v == "NEGATIVE" for v in peers.values())
            vision_source = provenance(sha, "vision.json")
            image_source = provenance(sha, camera + ".jpg")
            image_bytes = len(read(sha, camera + ".jpg"))
            matching = []
            for path, obj in index.get(snap["capture_time_ct"], []):
                cam_rows = [r for cell in obj["cells"] for r in cell["camera_rows"]
                            if r["camera_id"] == camera]
                matching.append({"source": provenance(OUTCOME_HEAD, path),
                                 "cycle_in_target_window": obj["cycle_in_target_predawn_dawn_window"],
                                 "vision_sha256_matches": obj["input_hashes"]["vision.json"] == vision_source["sha256"],
                                 "image_sha256_matches": any(r.get("latest_image_sha256") == image_source["sha256"] for r in cam_rows),
                                 "cells": [{k: v for k, v in cell.items() if k != "camera_rows"} for cell in obj["cells"]]})
            support = {}
            for path in ("status.json", "burst_status.json"):
                obj = json.loads(read(sha, path))
                support[path] = {"source": provenance(sha, path),
                                 "capture_identity_matches": obj["capture_time_ct"] == snap["capture_time_ct"],
                                 "camera_ok": obj["cameras"][camera].get("ok"),
                                 "shots": obj["cameras"][camera].get("shots")}
            case = {
                "case_id": f"{snap['capture_time_ct'][:19]}_{camera}",
                "capture_cycle_time_ct": snap["capture_time_ct"],
                "dawn_ct": snap.get("dawn_ct"), "camera_id": camera,
                "vision_source": vision_source,
                "positive_fields": {k: row[k] for k in SIGNAL_FIELDS
                                    if normalized(row.get(k)) in POSITIVE_VALUES[k]},
                "unique_same_site": unique,
                "camera_analysis": relevant_analysis(row),
                "peer_evidence": {p: {"scorer_state": states[p],
                                      "visibility": snap["cameras"][p].get("visibility"),
                                      "detectability": snap["cameras"][p].get("detectability"),
                                      "burst_shots": snap["cameras"][p].get("burst_shots"),
                                      "temporal_summary": snap["cameras"][p].get("temporal_summary")}
                                  for p in peers},
                "cross_camera_evidence": {k: v for k, v in snap.get("cross_camera", {}).items()
                                          if k in ("overall_visual_jubilee_signal", "montrose_visual_signal",
                                                   "point_clear_visual_signal", "temporal_confirmation",
                                                   "spatial_confirmation", "highest_value_observation",
                                                   "highest_value_temporal_change", "important_confounders",
                                                   "synthesis_mode")},
                "retained_image": {**image_source, "bytes": image_bytes,
                                   "last_shot_bytes_match": image_bytes == row["burst_shots"][-1]["bytes"],
                                   "image_review_scope": "canonical final image only; full three-frame burst not retained at root"},
                "capture_support": support,
                "observation_record_links": matching,
                "confirmed_event_date_matches": [e["event_id"] for e in events
                                                 if e.get("classification") == "confirmed_jubilee"
                                                 and e.get("event_date_ct") == snap["capture_time_ct"][:10]],
                "owner_reported_non_event_date_overlap": snap["capture_time_ct"].startswith("2026-09-12"),
            }
            positives.append(case)
            if unique:
                uniques.append(case)
    assert len(snapshots) == 931 and len(positives) == 21 and len(uniques) == 17
    for e in uniques:
        assert not e["confirmed_event_date_matches"]
        assert all(v["capture_identity_matches"] and v["camera_ok"] for v in e["capture_support"].values())
        assert e["retained_image"]["last_shot_bytes_match"]
        assert e["observation_record_links"] and all(
            r["vision_sha256_matches"] and r["image_sha256_matches"] for r in e["observation_record_links"])
    context = []
    for sha, snap in snapshots:
        t = datetime.fromisoformat(snap["capture_time_ct"])
        centers = (datetime.fromisoformat("2026-09-29T06:24:25.343684-05:00"),
                   datetime.fromisoformat("2026-09-28T05:39:11.063601-05:00"))
        if not any(abs(t - center) <= timedelta(hours=2) for center in centers):
            continue
        row = snap["cameras"]["montrose_pier_bird"]
        context.append({"source": provenance(sha, "vision.json"),
                        "capture_cycle_time_ct": snap["capture_time_ct"],
                        "state": observation_state(row),
                        "camera_analysis": {k: row.get(k) for k in (
                            "visibility", "detectability", "fish_surface_activity", "fish_jump_activity",
                            "repeated_surface_activity", "temporal_persistence", "temporal_summary",
                            "overall_jubilee_visual_signal", "artificial_light_confounding", "burst_shots")}})
    public = json.loads(read(OUTCOME_HEAD, evidence_paths[-1]))
    public_context = [r for key in ("records", "observations") for r in public.get(key, [])
                      if str(r.get("observation_start_ct", "")).startswith("2026-09-29T06:")]
    counts = Counter(e["camera_id"] for e in uniques)
    result = {
        "schema_version": "1.0", "scope": "PR76_RESEARCH_ONLY_CASE_INVESTIGATION",
        "production_action": "NO_CHANGE", "paid_model_calls": 0,
        "source_head_sha": SOURCE_HEAD, "scorer_source": provenance(RESEARCH_HEAD, scorer_path),
        "outcome_evidence_head_sha": OUTCOME_HEAD,
        "snapshot_count": len(snapshots), "positive_count": len(positives), "unique_count": len(uniques),
        "capture_range_ct": [snapshots[0][1]["capture_time_ct"], snapshots[-1][1]["capture_time_ct"]],
        "unique_camera_counts": {c: counts[c] for c in CAMERAS},
        "unique_positive_field_counts": dict(Counter(k for e in uniques for k in e["positive_fields"])),
        "cases": uniques, "non_unique_positive_context": [e for e in positives if not e["unique_same_site"]],
        "biological_case_temporal_context": context,
        "public_context_september_29": public_context,
        "outcome_evidence_sources": [provenance(OUTCOME_HEAD, p) for p in evidence_paths],
        "confirmed_2026_events": [e for e in events if e.get("event_date_ct", "").startswith("2026")],
        "august_29_30_replay_snapshot_count": sum(s["capture_time_ct"][:10] in ("2026-08-29", "2026-08-30") for _, s in snapshots),
        "limits": ["Camera positives are descriptive rubric observations, not event labels.",
                   "Same-cycle peers are sequential captures, not simultaneous observations.",
                   "Final-image review cannot independently establish burst persistence or absence.",
                   "No matched positive-event camera challenge; sensitivity, specificity and lead time are not estimable.",
                   "Outcome evidence is retrospective and not a pre-issue predictor."]
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("snapshot_count", "positive_count", "unique_count", "unique_camera_counts", "unique_positive_field_counts")}))


if __name__ == "__main__":
    main()

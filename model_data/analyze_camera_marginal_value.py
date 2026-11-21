#!/usr/bin/env python3
"""Offline camera marginal-value audit using repository history and usage summary.

No model/API calls are made. This script replays committed vision.json states,
scores camera-specific signal uniqueness within same-site groups, and joins
sanitized token usage from api_usage_summary.json.
"""
from __future__ import annotations
import argparse, json, subprocess
from collections import defaultdict
from pathlib import Path

CAMERAS = (
    "montrose_pier_bird","montrose_pier_boat","montrose_shoreline",
    "pcl_e2_back_deck","pcl_e2_bay_mouth","pcl_e3_bay_mouth",
)
SITE = {
    c: ("montrose" if c.startswith("montrose") else "point_clear")
    for c in CAMERAS
}
SIGNAL_FIELDS = (
    "overall_jubilee_visual_signal","temporal_jubilee_signal",
    "fish_surface_activity","fish_jump_activity","fish_gulping_or_smoking",
    "shrimp_surface_popping","shrimp_surface_concentration",
    "crab_surface_swimming","crab_climbing_structure",
    "flounder_or_flatfish_shallow","eel_displacement",
    "stingray_or_other_bottom_fauna_displacement",
    "shoreline_or_structure_accumulation",
    "offshore_bottom_fauna_surface_aggregation","bird_feeding_activity",
    "people_present","flashlight_activity","clustered_search_behavior",
    "people_collecting_seafood","animal_lethargy_or_abnormal_motion",
    "repeated_surface_activity",
)
# Only explicit observations in the existing rubric count as positives.
# Possible/weak labels, unavailable markers and unexpected values stay UNKNOWN.
NEGATIVE_VALUES = {"none", "none_visible", "no", "not_observed"}
POSITIVE_VALUES = {
    "overall_jubilee_visual_signal": [
        "moderate",
        "strong"
    ],
    "temporal_jubilee_signal": [
        "moderate",
        "strong"
    ],
    "visibility": [
        "poor",
        "fair",
        "good"
    ],
    "detectability": [
        "low",
        "moderate",
        "high"
    ],
    "fish_surface_activity": [
        "isolated",
        "clear_abnormal",
        "dense"
    ],
    "fish_jump_activity": [
        "isolated",
        "multiple",
        "dense"
    ],
    "fish_gulping_or_smoking": [
        "clear",
        "widespread"
    ],
    "shrimp_surface_popping": [
        "multiple",
        "dense"
    ],
    "shrimp_surface_concentration": [
        "clear",
        "dense"
    ],
    "crab_surface_swimming": [
        "clear",
        "multiple"
    ],
    "crab_climbing_structure": [
        "clear",
        "multiple"
    ],
    "flounder_or_flatfish_shallow": [
        "clear",
        "multiple"
    ],
    "eel_displacement": [
        "clear",
        "multiple"
    ],
    "stingray_or_other_bottom_fauna_displacement": [
        "clear",
        "multiple"
    ],
    "shoreline_or_structure_accumulation": [
        "clear",
        "dense"
    ],
    "offshore_bottom_fauna_surface_aggregation": [
        "clear",
        "dense"
    ],
    "bird_feeding_activity": [
        "active",
        "dense_active"
    ],
    "people_collecting_seafood": [
        "clear"
    ],
    "animal_lethargy_or_abnormal_motion": [
        "clear",
        "widespread"
    ],
    "people_present": [
        "clear"
    ],
    "flashlight_activity": [
        "clear"
    ],
    "clustered_search_behavior": [
        "clear"
    ],
    "repeated_surface_activity": [
        "clear"
    ]
}

def normalized(value):
    return value.strip().lower() if isinstance(value, str) else ""

def usable(row):
    return (
        isinstance(row, dict)
        and row.get("status") == "ok"
        and normalized(row.get("visibility")) in {"fair", "good"}
        and normalized(row.get("detectability")) in {"moderate", "high"}
    )

def observation_state(row):
    """Scoped descriptive evidence, never a training negative or confirmation."""
    if not usable(row):
        return "UNKNOWN"
    values = {key: normalized(row.get(key)) for key in SIGNAL_FIELDS}
    if any(value in POSITIVE_VALUES[key] for key, value in values.items()):
        return "POSITIVE"
    if all(value in NEGATIVE_VALUES for value in values.values()):
        return "NEGATIVE"
    return "UNKNOWN"

def has_signal(row):
    return observation_state(row) == "POSITIVE"

def score_snapshots(snapshots):
    keys = ("observations", "missing", "usable", "unknown", "negative", "signal",
            "comparable", "unique_signal", "unique_signal_unassessable",
            "site_disagreement")
    out = {c: dict.fromkeys(keys, 0) for c in CAMERAS}
    for snap in snapshots:
        cams = snap.get("cameras", {})
        states = {c: observation_state(cams.get(c)) for c in CAMERAS}
        for c in CAMERAS:
            s = out[c]
            row = cams.get(c)
            if row is None:
                s["missing"] += 1
            else:
                s["observations"] += 1
            if usable(row):
                s["usable"] += 1
            own = states[c]
            if own == "UNKNOWN":
                s["unknown"] += 1
                continue
            s["signal" if own == "POSITIVE" else "negative"] += 1
            peers = [states[p] for p in CAMERAS if p != c and SITE[p] == SITE[c]]
            known = [p for p in peers if p != "UNKNOWN"]
            if known:
                s["comparable"] += 1
                if any(p != own for p in known):
                    s["site_disagreement"] += 1
            if own == "POSITIVE":
                if all(p == "NEGATIVE" for p in peers):
                    s["unique_signal"] += 1
                elif "POSITIVE" not in peers and "UNKNOWN" in peers:
                    s["unique_signal_unassessable"] += 1
    return out

def usage_costs(groups, start_date=None, end_date=None):
    selected=[]
    for g in groups:
        d=g.get("date_ct","")
        if start_date and d < start_date: continue
        if end_date and d > end_date: continue
        selected.append(g)
    total=sum((g.get("tokens",{}).get("total_tokens",{}).get("known_sum") or 0) for g in selected)
    out={}
    for c in CAMERAS:
        stage="camera:"+c
        rows=[g for g in selected if g.get("stage")==stage]
        req=sum(g.get("completed_requests",0) or 0 for g in rows)
        tok=sum((g.get("tokens",{}).get("total_tokens",{}).get("known_sum") or 0) for g in rows)
        out[c]={"requests":req,"total_tokens":tok,"tokens_per_request":(tok/req if req else None),"share_of_selected_total":(tok/total if total else None)}
    return {"selected_total_tokens":total,"cameras":out}

def git_snapshots(repo, since=None, until=None):
    cmd=["git","-C",str(repo),"log","--format=%H","--","vision.json"]
    shas=subprocess.check_output(cmd,text=True).splitlines()
    snaps=[]
    for sha in shas:
        try:
            raw=subprocess.check_output(["git","-C",str(repo),"show",f"{sha}:vision.json"],text=True,stderr=subprocess.DEVNULL)
            obj=json.loads(raw)
        except Exception:
            continue
        t=obj.get("capture_time_ct") or ""
        if since and t and t < since: continue
        if until and t and t > until: continue
        snaps.append(obj)
    return snaps

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=".")
    ap.add_argument("--usage",default="api_usage_summary.json")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--output")
    ap.add_argument("--snapshots", help="Local JSON export of historical snapshots; no network or model calls")
    args=ap.parse_args()
    repo=Path(args.repo)
    usage=json.loads((repo/args.usage).read_text(encoding="utf-8"))
    snaps=git_snapshots(repo,args.since,args.until) if not args.snapshots else [
        entry.get("snapshot", entry) for entry in json.loads(Path(args.snapshots).read_text())
    ]
    if args.snapshots:
        snaps = [s for s in snaps if (not args.since or s.get("capture_time_ct", "") >= args.since)
                 and (not args.until or s.get("capture_time_ct", "") <= args.until)]
    result={
      "schema_version":"2.0",
      "method":"offline_git_replay_no_model_calls",
      "snapshot_count":len(snaps),
      "camera_signal_metrics":score_snapshots(snaps),
      "usage_metrics":usage_costs(usage.get("groups",[]), args.since[:10] if args.since else None, args.until[:10] if args.until else None),
      "guardrail":"Research only. Unique-signal absence on quiet history is insufficient to suppress a camera; positive/precursor challenge sets are required."
    }
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output: Path(args.output).write_text(text,encoding="utf-8")
    else: print(text,end="")

if __name__=="__main__":
    main()


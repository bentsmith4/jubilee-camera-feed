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
NO_SIGNAL = {"","none","none_visible","no","not_observed","not_assessable","uncertain","null","undefined"}

def has_signal(row):
    if not row or row.get("status") != "ok":
        return False
    for key in SIGNAL_FIELDS:
        value = str(row.get(key, "")).strip().lower()
        if value not in NO_SIGNAL:
            return True
    return False

def usable(row):
    if not row or row.get("status") != "ok":
        return False
    vis = str(row.get("visibility","")).lower()
    det = str(row.get("detectability","")).lower()
    return vis not in {"poor","very_poor","dark","unknown"} and det not in {"low","none","unknown"}

def score_snapshots(snapshots):
    out = {c: defaultdict(int) for c in CAMERAS}
    for snap in snapshots:
        cams = snap.get("cameras", {})
        for c in CAMERAS:
            row = cams.get(c)
            if row is None:
                continue
            s = out[c]
            s["observations"] += 1
            if usable(row): s["usable"] += 1
            own = has_signal(row)
            if own: s["signal"] += 1
            peers = [cams[p] for p in CAMERAS if p != c and SITE[p] == SITE[c] and p in cams]
            peer_sig = [has_signal(p) for p in peers]
            if own and peer_sig and not any(peer_sig): s["unique_signal"] += 1
            if peer_sig and any(v != own for v in peer_sig): s["site_disagreement"] += 1
    return {c: dict(v) for c,v in out.items()}

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
    args=ap.parse_args()
    repo=Path(args.repo)
    usage=json.loads((repo/args.usage).read_text(encoding="utf-8"))
    snaps=git_snapshots(repo,args.since,args.until)
    result={
      "schema_version":"1.0",
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

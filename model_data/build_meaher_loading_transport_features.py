#!/usr/bin/env python3
"""Build zero-weight Meaher oxygen-loading and Point Clear transport features.

This is a research/current-state feature layer, not a Jubilee probability model.
It uses only observations/model guidance available at or before the issue time.
"""
from __future__ import annotations
import argparse, csv, json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCO = ROOT / "model_data/arcos_realtime_normalized.csv"
NGOFS = ROOT / "model_data/ngofs2_point_clear_nowcast_normalized.csv"
OUT = ROOT / "model_data/meaher_loading_transport_features.json"

WINDOWS_H = (1, 3, 6)
DO_LEVELS = (2.0, 1.0, 0.5)
TRANSPORT_FRESHNESS_MIN = 180

def stamp(v):
    return datetime.fromisoformat(str(v).replace("Z","+00:00")).astimezone(timezone.utc)

def finite(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):
        return None

def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def available_at_issue(row, at):
    try:
        return stamp(row["available_at"]) <= at
    except (KeyError, TypeError, ValueError):
        return False

def latest_value(rows,param,at):
    xs=[r for r in rows if r.get("parameter")==param and stamp(r["observed_at"])<=at and available_at_issue(r,at)
        and r.get("qc_status") in ("ARCOS_RANGE_CHECK_PASS","SOURCE_QC_NOT_EXPOSED")]
    if not xs: return None
    return max(xs,key=lambda r:stamp(r["observed_at"]))

def series(rows,param,at,hours):
    lo=at.timestamp()-hours*3600
    out=[]
    for r in rows:
        if r.get("parameter")!=param or not available_at_issue(r,at): continue
        if r.get("qc_status") not in ("ARCOS_RANGE_CHECK_PASS","SOURCE_QC_NOT_EXPOSED"): continue
        t=stamp(r["observed_at"])
        v=finite(r.get("value"))
        if v is not None and lo <= t.timestamp() <= at.timestamp():
            out.append((t,v))
    return sorted(out)

def window_stats(points,hours):
    if not points:
        return {"hours":hours,"n":0,"min":None,"max":None,"mean":None,"delta":None,"slope_per_hour":None}
    vals=[v for _,v in points]
    first_t,first_v=points[0]; last_t,last_v=points[-1]
    elapsed=(last_t-first_t).total_seconds()/3600
    return {
      "hours":hours,"n":len(points),"min":min(vals),"max":max(vals),"mean":sum(vals)/len(vals),
      "delta":last_v-first_v,
      "slope_per_hour":((last_v-first_v)/elapsed if elapsed>0 else None),
      "first_observed_at":first_t.isoformat(),"last_observed_at":last_t.isoformat()
    }

def below_duration(points,threshold):
    if len(points)<2: return 0.0
    minutes=0.0
    for (t0,v0),(t1,_) in zip(points,points[1:]):
        if v0 < threshold:
            minutes += max(0,(t1-t0).total_seconds()/60)
    return round(minutes,3)

def transport_context(rows,issue):
    candidates=[]
    for r in rows:
        if r.get("evidence_class")!="MODEL": continue
        if r.get("parameter")!="shoreward_current" or r.get("vertical_role")!="bottom": continue
        try:
            valid=stamp(r["valid_at"])
            available=stamp(r["available_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if valid<=issue and available<=issue:
            v=finite(r.get("value"))
            if v is not None:
                candidates.append((valid,available,v,r))
    if not candidates:
        return {"status":"UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT","production_weight":0.0}
    valid,available,value,row=max(candidates,key=lambda x:x[0])
    age=(issue-valid).total_seconds()/60
    fresh=0<=age<=TRANSPORT_FRESHNESS_MIN
    return {
      "status":"KNOWN_ZERO_WEIGHT_MODEL_CONTEXT" if fresh else "UNKNOWN_STALE_MODEL_TRANSPORT",
      "shoreward_current_m_s":value if fresh else None,
      "valid_at":valid.isoformat(),"available_at":available.isoformat(),
      "age_minutes":round(age,3),"freshness_minutes":TRANSPORT_FRESHNESS_MIN,
      "source_class":"MODEL","station_name":row.get("station_name"),
      "vertical_position":"bottom","production_weight":0.0
    }

def build(root=ROOT,as_of=None):
    arcos=read_csv(root/"model_data/arcos_realtime_normalized.csv")
    mp=[r for r in arcos if r.get("station_id")=="DISL_ARCOS_MP" and r.get("source_stream")=="hydro"]
    do=[r for r in mp if r.get("parameter")=="dissolved_oxygen_mg_l"
        and r.get("qc_status")=="ARCOS_RANGE_CHECK_PASS"]
    if not do:
        return {"schema_version":"1.0","status":"UNKNOWN_NO_MEAHER_DO","production_action":"NO_CHANGE","production_weight":0.0}
    issue=stamp(as_of) if as_of else datetime.now(timezone.utc)
    do=[r for r in do if stamp(r["observed_at"])<=issue and available_at_issue(r,issue)]
    if not do:
        return {"schema_version":"1.0","status":"UNKNOWN_NO_MEAHER_DO_AT_ISSUE_TIME","production_action":"NO_CHANGE","production_weight":0.0}
    latest_do=latest_value(mp,"dissolved_oxygen_mg_l",issue)
    latest_pct=latest_value(mp,"dissolved_oxygen_percent",issue)
    latest_sal=latest_value(mp,"salinity_psu",issue)
    latest_temp=latest_value(mp,"water_temperature_c",issue)
    six=series(mp,"dissolved_oxygen_mg_l",issue,6)
    oxygen_windows={str(h):window_stats(series(mp,"dissolved_oxygen_mg_l",issue,h),h) for h in WINDOWS_H}
    sal_windows={str(h):window_stats(series(mp,"salinity_psu",issue,h),h) for h in WINDOWS_H}
    temp_windows={str(h):window_stats(series(mp,"water_temperature_c",issue,h),h) for h in WINDOWS_H}
    ngofs=read_csv(root/"model_data/ngofs2_point_clear_nowcast_normalized.csv")
    transport=transport_context(ngofs,issue)
    loading={
      "station_id":"DISL_ARCOS_MP","station_name":"Meaher Park",
      "issue_time_utc":issue.isoformat(),
      "dissolved_oxygen_mg_l":finite(latest_do["value"]) if latest_do else None,
      "dissolved_oxygen_percent":finite(latest_pct["value"]) if latest_pct else None,
      "salinity_psu":finite(latest_sal["value"]) if latest_sal else None,
      "water_temperature_c":finite(latest_temp["value"]) if latest_temp else None,
      "latest_observed_at":stamp(latest_do["observed_at"]).isoformat() if latest_do else None,
      "historical_sensor_height_above_bottom_m":finite(latest_do.get("historical_sensor_height_above_bottom_m")) if latest_do else None,
      "current_geometry_status":latest_do.get("depth_geometry_status") if latest_do else "UNKNOWN",
      "oxygen_windows":oxygen_windows,
      "salinity_windows":sal_windows,
      "temperature_windows":temp_windows,
      "minutes_below_do_mg_l":{str(x):below_duration(six,x) for x in DO_LEVELS},
      "production_weight":0.0
    }
    combined_status=("RESEARCH_FEATURES_AVAILABLE" if transport["status"]=="KNOWN_ZERO_WEIGHT_MODEL_CONTEXT"
                     else "LOADING_AVAILABLE_TRANSPORT_UNKNOWN")
    return {
      "schema_version":"1.0","status":combined_status,
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "issue_time_utc":issue.isoformat(),
      "scope":"Meaher oxygen-loading state plus Point Clear modeled transport context",
      "loading":loading,"transport":transport,
      "interactions":{
        "low_do_x_shoreward_transport":(
          loading["dissolved_oxygen_mg_l"] * transport["shoreward_current_m_s"]
          if loading["dissolved_oxygen_mg_l"] is not None and transport.get("shoreward_current_m_s") is not None else None
        ),
        "interpretation":"Diagnostic interaction only; sign/magnitude has no production meaning until held-out event/control validation."
      },
      "leakage_guard":"Only source rows with observation/valid time and availability at or before issue time are eligible.",
      "production_action":"NO_CHANGE","production_weight":0.0,
      "predictive_validity":"NOT_ESTABLISHED"
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=ROOT)
    ap.add_argument("--as-of")
    args=ap.parse_args()
    result=build(args.root,args.as_of)
    out=args.root/"model_data/meaher_loading_transport_features.json"
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=="__main__":
    main()

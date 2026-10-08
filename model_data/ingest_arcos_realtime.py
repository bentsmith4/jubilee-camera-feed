#!/usr/bin/env python3
"""Ingest public DISL ARCOS near-real-time hydrographic and meteorological observations.

Research/current-state context only. This collector never changes Jubilee
probabilities, alert gates, camera cadence, or production feature weights.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "arcos_realtime_sources.json"
ENDPOINT = "https://g.disl.edu/api/ds/query?ds_type=grafana-postgresql-datasource&requestId=JUBILEE"

HYDRO_PARAMETERS = (
    ("water_temperature_c", "Water Temperature", "degC"),
    ("salinity_psu", "Salinity", "PSU"),
    ("dissolved_oxygen_percent", "Dissolved Oxygen %", "%"),
    ("dissolved_oxygen_mg_l", "Dissolved Oxygen", "mg/L"),
    ("turbidity_fnu", "Turbidity", "FNU"),
    ("pressure_psi", "Pressure", "psi"),
    ("depth_field_m", "Depth", "m"),
)
MET_PARAMETERS = (
    ("air_temperature_c", "Air Temperature", "degC"),
    ("relative_humidity_percent", "Relative Humidity", "%"),
    ("barometric_pressure_inhg", "Barometric Pressure", "inHg"),
    ("precipitation", "Precipitation", "source_native"),
    ("wind_speed", "Wind Speed", "source_native"),
    ("wind_direction_deg", "Wind Direction", "degree"),
    ("quantum_radiation_umol_m2_s", "Quantum Radiation", "umol/m2/s"),
    ("solar_radiation_kw_m2", "Solar Radiation", "kW/m2"),
)

def finite(value):
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None

def build_query(station_key, start, end, config, stream="hydro"):
    allowed={s["station_key"] for s in config["stations"]}
    if station_key not in allowed:
        raise ValueError("station key is not allowlisted")
    if stream == "hydro":
        table=station_key + "_hyd_sum"
        sql=f"""SELECT
  time_bucket('1800.000s',ts) AS "time"
  , avg(watertemp1_avg) AS "Water Temperature"
  , avg(salinity1_avg) AS "Salinity"
  , avg(dis_oxy1_avg) AS "Dissolved Oxygen %"
  , avg(dis_oxy2_avg) AS "Dissolved Oxygen"
  , avg(turbidity1_avg) AS "Turbidity"
  , avg(pressure) AS "Pressure"
  , avg(depth1_avg) AS "Depth"
FROM
  {table}
WHERE
  ts BETWEEN '{start.isoformat().replace("+00:00","Z")}' AND '{end.isoformat().replace("+00:00","Z")}'
  AND watertemp1_avg BETWEEN -5 AND 45
GROUP BY
  time
ORDER BY
  time asc"""
    elif stream == "met":
        table=station_key + "_met_min"
        precip_expr=("SUM(precip1) / 25.4" if station_key in ("bsp","mp") else "SUM(precip1)")
        sql=f"""SELECT
  time_bucket('1800.000s',ts) AS "time"
  , avg(airtemp1) AS "Air Temperature"
  , avg(relhumid1_avg) AS "Relative Humidity"
  , avg(bar_pressure1) AS "Barometric Pressure"
  , {precip_expr} AS "Precipitation"
  , avg(windspeed1) AS "Wind Speed"
  , CASE
      WHEN DEGREES(ATAN2(SUM(SIN(RADIANS(winddir1))),SUM(COS(RADIANS(winddir1))))) < 0
      THEN 360 + DEGREES(ATAN2(SUM(SIN(RADIANS(winddir1))),SUM(COS(RADIANS(winddir1)))))
      ELSE DEGREES(ATAN2(SUM(SIN(RADIANS(winddir1))),SUM(COS(RADIANS(winddir1)))))
    END AS "Wind Direction"
  , AVG(quantumrad1) AS "Quantum Radiation"
  , AVG(solarrad1) AS "Solar Radiation"
FROM
  {table}
WHERE
  ts BETWEEN '{start.isoformat().replace("+00:00","Z")}' AND '{end.isoformat().replace("+00:00","Z")}'
GROUP BY
  time
ORDER BY
  time asc"""
    else:
        raise ValueError("stream must be hydro or met")
    return {
      "queries":[{
        "refId":"A",
        "datasource":{"type":"grafana-postgresql-datasource","uid":config["datasource_uid"]},
        "rawSql":sql,
        "format":"table",
        "datasourceId":config["datasource_id"],
        "intervalMs":config["aggregation_minutes"]*60_000,
        "maxDataPoints":500
      }],
      "from":str(int(start.timestamp()*1000)),
      "to":str(int(end.timestamp()*1000))
    }

def fetch(payload):
    body=json.dumps(payload,separators=(",",":")).encode()
    req=urllib.request.Request(
        ENDPOINT,data=body,method="POST",
        headers={
          "Content-Type":"application/json","Accept":"application/json",
          "User-Agent":"jubilee-research/3.1","Origin":"https://g.disl.edu",
          "Referer":"https://g.disl.edu/"
        })
    last=None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req,timeout=15) as response:
                raw=response.read(5_000_001)
            if len(raw)>5_000_000:
                raise ValueError("ARCOS response exceeds bounded fetch limit")
            return raw
        except (OSError,TimeoutError) as exc:
            last=exc
            if attempt==1: raise
            time.sleep(2**attempt)
    raise last

def parse_response(raw, station, retrieved_at, config, stream=None):
    doc=json.loads(raw)
    result=doc.get("results",{}).get("A",{})
    if result.get("error") or result.get("status", 200) != 200:
        raise ValueError("ARCOS datasource query failed")
    frames=result.get("frames",[])
    if not frames:
        return []
    rows=[]
    ranges=config["source_ranges"]
    for frame in frames:
        schema=frame.get("schema",{}).get("fields",[])
        values=frame.get("data",{}).get("values",[])
        if not schema or not values or len(schema)!=len(values):
            continue
        columns={f.get("name"): vals for f,vals in zip(schema,values)}
        labels=set(columns)
        detected=("hydro" if "Dissolved Oxygen" in labels or "Salinity" in labels
                  else "met" if "Air Temperature" in labels or "Wind Speed" in labels else stream)
        parameters=HYDRO_PARAMETERS if detected=="hydro" else MET_PARAMETERS if detected=="met" else ()
        times=columns.get("time",[])
        for idx,ms in enumerate(times):
            if ms is None: continue
            observed=datetime.fromtimestamp(float(ms)/1000,tz=timezone.utc)
            for parameter,label,unit in parameters:
                vals=columns.get(label,[])
                if idx>=len(vals): continue
                value=finite(vals[idx])
                if value is None: continue
                final_unit=unit
                if detected=="met" and parameter=="precipitation":
                    final_unit="in" if station["station_key"] in ("bsp","mp") else "mm"
                if detected=="met" and parameter=="wind_speed":
                    final_unit="kn"
                range_status="NOT_RANGE_SCREENED"
                if parameter in ranges:
                    lo,hi=ranges[parameter]
                    range_status="ARCOS_RANGE_CHECK_PASS" if lo<=value<=hi else "ARCOS_RANGE_CHECK_FAIL"
                elif parameter=="depth_field_m":
                    range_status="SOURCE_QC_NOT_EXPOSED"
                geometry=("UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION"
                          if detected=="hydro" and (parameter=="depth_field_m" or not station.get("current_sensor_height_above_bed_verified"))
                          else "NOT_APPLICABLE" if detected=="met" else "VERIFIED_GEOMETRY")
                rows.append({
                  "source_id":"disl_arcos_realtime_public_grafana",
                  "source_stream":detected,
                  "station_id":station["station_id"],"station_key":station["station_key"],
                  "station_name":station["name"],"latitude":station.get("latitude"),
                  "longitude":station.get("longitude"),"station_role":station["role"],
                  "parameter":parameter,"value":value,"unit":final_unit,
                  "observed_at":observed.isoformat(),"available_at":retrieved_at.isoformat(),
                  "ingested_at":retrieved_at.isoformat(),"qc_status":range_status,
                  "source_qc_status":"SOURCE_QC_NOT_EXPOSED_IN_PUBLIC_GRAFANA_FRAME",
                  "depth_geometry_status":geometry,
                  "historical_sensor_height_above_bottom_m":station.get("historical_sensor_height_above_bottom_m"),
                  "historical_geometry_evidence_status":station.get("historical_geometry_evidence_status","UNKNOWN"),
                  "is_direct_station_observation":True,
                  "is_direct_local_bottom_measurement":False,
                  "production_weight":0.0,
                  "source_url":station.get("source_url","https://www.disl.edu/arcos/")
                })
    return rows

def archive_raw(raw, station_key, stream):
    digest=hashlib.sha256(raw).hexdigest()
    path=HERE/"raw_arcos_realtime"/f"{station_key}_{stream}.json.gz"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(gzip.compress(raw,mtime=0))
    return str(path.relative_to(HERE)),digest,len(raw)

def write_csv(rows,path):
    if not rows:
        return
    tmp=path.with_suffix(".tmp")
    fields=list(rows[0])
    with tmp.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader(); w.writerows(rows)
    tmp.replace(path)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--hours",type=int,default=None)
    ap.add_argument("--as-of")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    config=json.loads(CONFIG.read_text(encoding="utf-8"))
    now=datetime.fromisoformat(args.as_of.replace("Z","+00:00")) if args.as_of else datetime.now(timezone.utc)
    now=now.astimezone(timezone.utc)
    hours=args.hours or config["poll_window_hours"]
    start=now-timedelta(hours=hours)
    manifest={
      "schema_version":"1.1","retrieved_at_utc":now.isoformat(),
      "source":"DISL ARCOS public Grafana","endpoint":ENDPOINT.split("?")[0],
      "aggregation_minutes":config["aggregation_minutes"],
      "freshness_minutes":config["freshness_minutes"],"status":"failed",
      "production_action":"NO_CHANGE","stations":[]
    }
    all_rows=[]
    for station in config["stations"]:
        entry={"station_id":station["station_id"],"station_key":station["station_key"],
               "station_name":station["name"],"streams":[]}
        for stream in ("hydro","met"):
            payload=build_query(station["station_key"],start,now,config,stream)
            if args.dry_run:
                print(json.dumps({"station":station["station_key"],"stream":stream,"query":payload},indent=2))
                continue
            part={"stream":stream}
            try:
                raw=fetch(payload)
                raw_path,digest,size=archive_raw(raw,station["station_key"],stream)
                retrieved=datetime.now(timezone.utc)
                rows=parse_response(raw,station,retrieved,config,stream)
                all_rows.extend(rows)
                times=sorted({r["observed_at"] for r in rows})
                part.update({"status":"complete" if rows else "empty","retrieved_at_utc":retrieved.isoformat(),"raw_path":raw_path,
                             "raw_sha256":digest,"raw_bytes":size,"normalized_rows":len(rows),
                             "latest_observed_at":max(times) if times else None})
            except Exception as exc:
                part.update({"status":"failed","error_type":type(exc).__name__,"normalized_rows":0})
            entry["streams"].append(part)
        statuses=[x["status"] for x in entry["streams"]]
        entry["status"]="complete" if "complete" in statuses else "empty" if "empty" in statuses else "failed"
        entry["normalized_rows"]=sum(x.get("normalized_rows",0) for x in entry["streams"])
        entry["latest_observed_at"]=max((x["latest_observed_at"] for x in entry["streams"] if x.get("latest_observed_at")),default=None)
        manifest["stations"].append(entry)
    if args.dry_run: return
    all_rows.sort(key=lambda r:(r["observed_at"],r["station_id"],r["source_stream"],r["parameter"]))
    if all_rows:
        write_csv(all_rows,HERE/"arcos_realtime_normalized.csv")
    else:
        (HERE/"arcos_realtime_normalized.csv").write_text("", encoding="utf-8")
    good=[s for s in manifest["stations"] if s["status"]=="complete"]
    manifest["retrieved_at_utc"]=datetime.now(timezone.utc).isoformat()
    manifest["normalized_rows"]=len(all_rows)
    manifest["stations_with_current_data"]=[s["station_id"] for s in good]
    manifest["parameters_seen"]=sorted({r["parameter"] for r in all_rows})
    manifest["status"]="complete" if len(good)==len(manifest["stations"]) else ("partial" if good else "unavailable")
    manifest["guardrails"]=[
      "Direct at named ARCOS stations; regional/oxygen-loading/weather context for Jubilee unless station geometry proves otherwise.",
      "Public Grafana frame does not expose source aggregate QC per observation; DISL physical range checks are applied locally.",
      "Historical 0.5 m-above-bottom evidence is retained separately and is not automatically treated as current deployment geometry.",
      "Depth field is not accepted as sensor height above bed; current bottom identity remains unverified unless station-specific current metadata proves it.",
      "Missing, empty, stale, or range-rejected values remain UNKNOWN.",
      "All rows retain production_weight=0.0 pending held-out promotion."
    ]
    (HERE/"arcos_realtime_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2))
    if manifest["status"]=="failed":
        raise SystemExit(1)

if __name__=="__main__":
    main()

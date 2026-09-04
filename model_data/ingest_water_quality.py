#!/usr/bin/env python3
"""Ingest public Water Quality Portal records for Jubilee-model research.

This script intentionally produces research/backtest data only. It does not alter
production Jubilee probabilities. Raw downloads and normalized rows are retained
separately so provenance can be audited.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
REGISTRY = HERE / "water_quality_sources.json"
RAW_DIR = HERE / "raw_water_quality"
OUT_CSV = HERE / "water_quality_normalized.csv"
MANIFEST = HERE / "water_quality_ingest_manifest.json"
WQP = "https://www.waterqualitydata.us/data/Result/search"


def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "jubilee-model-research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def wqp_url(station_ids):
    params = {
        "siteid": ";".join(station_ids),
        "mimeType": "csv",
        "zip": "no",
        "providers": "STORET",
        "sorted": "no",
    }
    return WQP + "?" + urllib.parse.urlencode(params, safe=";")


def first(row, *keys):
    for key in keys:
        val = row.get(key)
        if val not in (None, ""):
            return val
    return ""


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize(raw_csv: bytes, source_id: str, station_cell: dict):
    text = raw_csv.decode("utf-8-sig", errors="replace")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        station = first(r, "MonitoringLocationIdentifier", "Monitoring Location Identifier")
        value = as_float(first(r, "ResultMeasureValue", "Result Measure Value"))
        unit = first(r, "MeasureUnitCode", "ResultMeasure/MeasureUnitCode", "Result Measure/Measure Unit Code")
        char = first(r, "CharacteristicName", "Characteristic Name")
        date = first(r, "ActivityStartDate", "Activity Start Date")
        time = first(r, "ActivityStartTime/Time", "Activity Start Time/Time")
        tz = first(r, "ActivityStartTime/TimeZoneCode", "Activity Start Time/Time Zone Code")
        lat = as_float(first(r, "LatitudeMeasure", "Latitude Measure"))
        lon = as_float(first(r, "LongitudeMeasure", "Longitude Measure"))
        depth = as_float(first(r, "ActivityDepthHeightMeasure/MeasureValue", "Activity Depth Height Measure/Measure Value"))
        depth_unit = first(r, "ActivityDepthHeightMeasure/MeasureUnitCode", "Activity Depth Height Measure/Measure Unit Code")
        qc = first(r, "ResultStatusIdentifier", "Result Status Identifier", "ResultDetectionConditionText")
        rows.append({
            "source_id": source_id,
            "provider": "Water Quality Portal/STORET",
            "station_id": station,
            "station_name": first(r, "MonitoringLocationName", "Monitoring Location Name"),
            "shoreline_cell": station_cell.get(station, "regional"),
            "sample_date": date,
            "sample_time": time,
            "sample_timezone": tz,
            "parameter": char,
            "value": value,
            "unit": unit,
            "latitude": lat,
            "longitude": lon,
            "depth": depth,
            "depth_unit": depth_unit,
            "qc_or_status": qc,
            "activity_type": first(r, "ActivityTypeCode", "Activity Type Code"),
            "method": first(r, "ResultAnalyticalMethod/MethodIdentifier", "Result Analytical Method/Method Identifier"),
            "organization": first(r, "OrganizationIdentifier", "Organization Identifier"),
            "source_url": WQP,
            "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
            "production_weight": 0.0,
        })
    return rows


def write_csv(rows):
    if not rows:
        return
    fields = list(rows[0])
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print URLs and registry without downloading")
    args = parser.parse_args()
    reg = load_registry()
    RAW_DIR.mkdir(exist_ok=True)
    all_rows = []
    manifest = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "sources": [], "status": "running"}
    for source in reg["source_families"]:
        if "waterqualitydata.us" not in source.get("endpoint", ""):
            continue
        ids = [s["station_id"] for s in source["stations"]]
        cells = {s["station_id"]: s.get("shoreline_cell", "regional") for s in source["stations"]}
        url = wqp_url(ids)
        entry = {"source_id": source["source_id"], "url": url, "stations": ids}
        if args.dry_run:
            print(json.dumps(entry, indent=2))
            continue
        try:
            payload = fetch(url)
            raw_path = RAW_DIR / f"{source['source_id'].lower()}.csv"
            raw_path.write_bytes(payload)
            rows = normalize(payload, source["source_id"], cells)
            all_rows.extend(rows)
            entry.update({"status": "ok", "raw_path": str(raw_path.relative_to(HERE)), "rows": len(rows)})
        except Exception as exc:
            entry.update({"status": "error", "error": repr(exc)})
        manifest["sources"].append(entry)
    if not args.dry_run:
        write_csv(all_rows)
        manifest.update({"finished_at_utc": datetime.now(timezone.utc).isoformat(), "normalized_rows": len(all_rows), "status": "complete"})
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Ingest current Weeks Bay NERRS observations through NOAA NDBC.

This source is DIRECT for the WKQA1/WKXA1 stations and a PROXY for Eastern
Shore open-bay Jubilee physics. It is never relabeled as local Montrose,
Fairhope, or Point Clear bottom water quality.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OCEAN_URL = "https://www.ndbc.noaa.gov/data/realtime2/WKQA1.ocean"
MET_URL = "https://www.ndbc.noaa.gov/data/realtime2/WKXA1.txt"
STATIONS = {
    "WKQA1": {"name": "Fish River, Weeks Bay Reserve, AL", "lat": 30.417, "lon": -87.823, "class": "DIRECT_STATION_PROXY_EASTERN_SHORE"},
    "WKXA1": {"name": "Safe Harbor Met Station, Weeks Bay Reserve, AL", "lat": 30.421, "lon": -87.828, "class": "DIRECT_STATION_MET_PROXY_EASTERN_SHORE"},
}


def finite(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "jubilee-research/2.2"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = response.read(5_000_001)
            if len(payload) > 5_000_000:
                raise ValueError("Weeks Bay source exceeded bounded fetch limit")
            return payload
        except (OSError, TimeoutError) as exc:
            last = exc
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise last  # pragma: no cover


def _split_table(text: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    headers = [ln for ln in lines if ln.startswith("#")]
    data = [ln for ln in lines if not ln.startswith("#") and not ln.startswith("-")]
    if not headers:
        raise ValueError("NDBC payload missing header")
    names = headers[0].lstrip("#").split()
    # NDBC sometimes prefixes STN in hourly aggregate files, while station files do not.
    return names, [row.split() for row in data]


def _timestamp(parts):
    year, month, day, hour, minute = map(int, parts[:5])
    if year < 100:
        year += 2000 if year < 70 else 1900
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def parse_ocean(text: str, retrieved_at: datetime):
    headers, records = _split_table(text)
    # Normalize known variants in the NDBC ocean header.
    aliases = {"#YY": "YY", "YY": "YY", "O2%": "O2PCT"}
    headers = [aliases.get(h, h) for h in headers]
    rows = []
    variable_map = {
        "DEPTH": ("depth", "m"),
        "OTMP": ("water_temperature", "degC"),
        "COND": ("conductivity", "mS/cm"),
        "SAL": ("salinity", "psu"),
        "O2PCT": ("dissolved_oxygen_percent", "%"),
        "O2PPM": ("dissolved_oxygen", "mg/L"),
        "CLCON": ("chlorophyll", "ug/L"),
        "TURB": ("turbidity", "FTU"),
        "PH": ("pH", "1"),
        "EH": ("redox_potential", "mV"),
    }
    for record in records:
        if len(record) < 5:
            continue
        station = "WKQA1"
        offset = 0
        if headers and headers[0] in ("STN", "-Sub"):
            station, offset = record[0], 1
        if station != "WKQA1":
            continue
        observed = _timestamp(record[offset:offset + 5])
        values = record[offset + 5:]
        value_headers = headers[offset + 5:]
        for key, raw in zip(value_headers, values):
            if key not in variable_map or raw in ("MM", "-", "NaN"):
                continue
            value = finite(raw)
            if value is None:
                continue
            parameter, unit = variable_map[key]
            rows.append({
                "source_id": "nerrs_weeks_bay_wkqa1_ndbc_realtime",
                "station_id": station,
                "station_name": STATIONS[station]["name"],
                "lat": STATIONS[station]["lat"], "lon": STATIONS[station]["lon"],
                "shoreline_cell": "Weeks Bay proxy",
                "evidence_class": STATIONS[station]["class"],
                "parameter": parameter, "value": value, "unit": unit,
                "depth_m": None,
                "observed_at": observed.isoformat(),
                "available_at": retrieved_at.isoformat(),
                "ingested_at": retrieved_at.isoformat(),
                "qc_status": "NDBC_REALTIME_AUTOMATED_QC",
                "production_weight": 0.0,
            })
    # attach reported sampling depth to measurements at the same timestamp when available
    depth_by_time = {r["observed_at"]: r["value"] for r in rows if r["parameter"] == "depth"}
    for row in rows:
        row["depth_m"] = depth_by_time.get(row["observed_at"])
    return rows


def parse_met(text: str, retrieved_at: datetime):
    headers, records = _split_table(text)
    headers = [h.lstrip("#") for h in headers]
    rows = []
    variable_map = {
        "WDIR": ("wind_direction", "degree_true"),
        "WSPD": ("wind_speed", "m/s"),
        "GST": ("wind_gust", "m/s"),
        "PRES": ("air_pressure", "hPa"),
        "ATMP": ("air_temperature", "degC"),
        "DEWP": ("dew_point", "degC"),
    }
    for record in records:
        if len(record) < 5:
            continue
        station = "WKXA1"
        offset = 0
        if headers and headers[0] == "STN":
            station, offset = record[0], 1
        if station != "WKXA1":
            continue
        observed = _timestamp(record[offset:offset + 5])
        values = record[offset + 5:]
        value_headers = headers[offset + 5:]
        for key, raw in zip(value_headers, values):
            if key not in variable_map or raw in ("MM", "-", "NaN"):
                continue
            value = finite(raw)
            if value is None:
                continue
            parameter, unit = variable_map[key]
            rows.append({
                "source_id": "nerrs_weeks_bay_wkxa1_ndbc_realtime",
                "station_id": station,
                "station_name": STATIONS[station]["name"],
                "lat": STATIONS[station]["lat"], "lon": STATIONS[station]["lon"],
                "shoreline_cell": "Weeks Bay proxy",
                "evidence_class": STATIONS[station]["class"],
                "parameter": parameter, "value": value, "unit": unit,
                "depth_m": None,
                "observed_at": observed.isoformat(),
                "available_at": retrieved_at.isoformat(),
                "ingested_at": retrieved_at.isoformat(),
                "qc_status": "NDBC_REALTIME_AUTOMATED_QC",
                "production_weight": 0.0,
            })
    return rows


def _archive(payload: bytes, source_name: str):
    digest = hashlib.sha256(payload).hexdigest()
    dest = HERE / "public_archive" / "ndbc" / f"{source_name}-{digest}.txt.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes(gzip.compress(payload, mtime=0))
    return digest, str(dest.relative_to(HERE))


def main():
    retrieved = datetime.now(timezone.utc)
    manifest = {
        "schema_version": "1.0", "retrieved_at": retrieved.isoformat(),
        "sources": [], "status": "failed", "production_action": "NO_CHANGE",
    }
    all_rows = []
    for source_name, url, parser in (
        ("WKQA1", OCEAN_URL, parse_ocean),
        ("WKXA1", MET_URL, parse_met),
    ):
        try:
            payload = _fetch(url)
            digest, archive = _archive(payload, source_name)
            rows = parser(payload.decode("utf-8", errors="strict"), retrieved)
            all_rows.extend(rows)
            latest = max((r["observed_at"] for r in rows), default=None)
            manifest["sources"].append({
                "station_id": source_name, "url": url, "raw_sha256": digest,
                "raw_path": archive, "normalized_rows": len(rows),
                "latest_observed_at": latest, "status": "complete" if rows else "empty",
            })
        except Exception as exc:
            manifest["sources"].append({
                "station_id": source_name, "url": url, "status": "failed",
                "error_type": type(exc).__name__, "normalized_rows": 0,
            })
    if all_rows:
        dest = HERE / "weeks_bay_realtime_normalized.csv"
        with dest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
            writer.writeheader(); writer.writerows(sorted(all_rows, key=lambda r: (r["observed_at"], r["station_id"], r["parameter"])))
    manifest["normalized_rows"] = len(all_rows)
    manifest["status"] = "complete" if all(x["status"] == "complete" for x in manifest["sources"]) else ("partial" if all_rows else "failed")
    manifest["guardrails"] = [
        "WKQA1 is direct only at Fish River/Weeks Bay and remains a regional proxy for Eastern Shore open-bay bottom state.",
        "NDBC realtime data have automated realtime QC; final archival NERRS/CDMO QA/QC may later revise values.",
        "available_at is conservatively set to retrieval time, not observation time.",
        "No source value changes Jubilee production weights without held-out validation."
    ]
    (HERE / "weeks_bay_realtime_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

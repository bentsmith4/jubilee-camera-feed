#!/usr/bin/env python3
"""Official AWC METAR observations; airport context, never shoreline measurements.

The dawn consumer must call current_snapshot at its issue time (or use
--snapshot-only --as-of). Retrieval success does not imply fresh/complete weather.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://aviationweather.gov/api/data/metar?ids=KBFM%2CKMOB&format=json&hours=6"
STATIONS = {
    "KBFM": ("Mobile Downtown Airport", 30.6147, -88.0630),
    "KMOB": ("Mobile Regional Airport", 30.6882, -88.2459),
}
# Native API units are retained. Accumulation periods must never be summed.
FIELDS = {
    "wspd": ("wind_speed", "kt", 0, 200),
    "wdir": ("wind_direction", "degree_true", 0, 360),
    "wgst": ("wind_gust", "kt", 0, 250),
    "temp": ("air_temperature", "degC", -60, 60),
    "dewp": ("dew_point", "degC", -80, 40),
    "slp": ("sea_level_pressure", "hPa", 850, 1100),
    "precip": ("precipitation_1h", "in", 0, 30),
    "pcp3hr": ("precipitation_3h", "in", 0, 60),
    "pcp6hr": ("precipitation_6h", "in", 0, 80),
    "pcp24hr": ("precipitation_24h", "in", 0, 100),
}
MANIFEST = "asos_weather_manifest.json"
NORMALIZED = "asos_weather_normalized.json"
SNAPSHOT = "current_asos_weather.json"


def utc(value):
    """Require timezone-aware timestamps; never infer local time."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def observation_time(report):
    value = number(report.get("obsTime"))
    try:
        return datetime.fromtimestamp(value, timezone.utc) if value is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def freshness_limit():
    return json.loads((HERE / "sensor_contract.json").read_text())["freshness_minutes"]["weather"]


def normalize(payload, retrieved_at, previous=()):
    """Select the newest report per airport, never fill holes from older reports."""
    if not isinstance(payload, list) or any(not isinstance(x, dict) for x in payload):
        raise ValueError("AWC METAR response must be a list of objects")
    old = {r.get("observation_id"): r for r in previous if isinstance(r, dict)}
    limit = freshness_limit()
    rows = []
    rejected = []
    for station, (name, lat, lon) in STATIONS.items():
        reports = []
        for report in payload:
            if report.get("icaoId") != station:
                continue
            observed = observation_time(report)
            if observed is None:
                rejected.append({"station_id": station, "reason": "INVALID_OBSERVATION_TIME"})
                continue
            reports.append(report)
        if not reports:
            continue
        report = max(reports, key=lambda r: (
            observation_time(r), utc(r.get("receiptTime")) or datetime.min.replace(tzinfo=timezone.utc),
            str(r.get("rawOb", ""))))
        observed = observation_time(report)
        received = utc(report.get("receiptTime"))
        raw = report.get("rawOb")
        raw = raw if isinstance(raw, str) else ""
        tokens = raw.replace("=", "").split()
        identity_tokens = tokens[1:] if tokens[:1] in (["METAR"], ["SPECI"]) else tokens
        issues = []
        if not identity_tokens or identity_tokens[0] != station:
            issues.append("STATION_IDENTITY_MISMATCH")
        if report.get("metarType") not in ("METAR", "SPECI") or "NIL" in tokens:
            issues.append("INVALID_REPORT_TYPE")
        if observed > retrieved_at:
            issues.append("FUTURE_OBSERVATION")
        if (retrieved_at - observed).total_seconds() > limit * 60:
            issues.append("STALE")
        if report.get("receiptTime") and received is None:
            issues.append("INVALID_RECEIPT_TIME")
        if received and not observed <= received <= retrieved_at:
            issues.append("INVALID_RECEIPT_ORDER")
        if "$" in tokens:
            issues.append("STATION_MAINTENANCE_FLAG")
        for field, expected in (("lat", lat), ("lon", lon)):
            actual = number(report.get(field))
            if actual is None or abs(actual - expected) > 0.05:
                issues.append("STATION_LOCATION_MISMATCH")
        # Include the entire decoded report: a changed/corrected payload is newly
        # available even when the observation time and raw METAR are unchanged.
        identity = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
        available = retrieved_at
        prior = utc(old.get(identity, {}).get("available_at"))
        if prior and observed <= prior <= retrieved_at and (received is None or received <= prior):
            available = prior
        for field, (parameter, unit, low, high) in FIELDS.items():
            raw_value = report.get(field)
            value = number(raw_value)
            flags = list(issues)
            state = "KNOWN"
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                flags.append("MISSING_VALUE")
            elif value is None or not low <= value <= high:
                flags.append("INVALID_OR_OUT_OF_RANGE")
            if field == "wdir" and (raw_value == "VRB" or number(report.get("wspd")) == 0):
                flags = list(issues) + ["VARIABLE_OR_CALM_DIRECTION"]
            if field == "wgst" and value is not None and number(report.get("wspd")) is not None and value < number(report["wspd"]):
                flags.append("GUST_BELOW_SUSTAINED_WIND")
            if field == "dewp" and value is not None and number(report.get("temp")) is not None and value > number(report["temp"]) + 1:
                flags.append("DEW_POINT_ABOVE_TEMPERATURE")
            if field in ("precip", "pcp3hr", "pcp6hr", "pcp24hr"):
                if any(t in tokens for t in ("PNO", "PWINO")):
                    flags.append("PRECIPITATION_SENSOR_UNAVAILABLE")
                trace = {"precip": "P0000", "pcp3hr": "60000", "pcp6hr": "60000", "pcp24hr": "70000"}[field]
                if not flags and trace in tokens:
                    # Trace is evidence of precipitation, not measured zero or
                    # an invented exact quantity (some decoders use 0.005 in).
                    state, value = "TRACE", None
            if flags:
                state, value = "UNKNOWN", None
            rows.append({
                "sensor_id": station, "station_name": name,
                "latitude": lat, "longitude": lon, "parameter": parameter,
                "value": value, "unit": unit, "value_status": state,
                "observed_at_utc": observed.isoformat(),
                "received_at_utc": received.isoformat() if received else None,
                "source_report_time": report.get("reportTime"),
                "available_at": available.isoformat(), "ingested_at": retrieved_at.isoformat(),
                "availability_basis": "first_successful_local_retrieval",
                "depth_m": None, "vertical_reference": "airport_surface_meteorology",
                "qc_flag": "|".join(sorted(set(flags))) if flags else "LOCAL_CHECKS_PASS",
                "source_qc_field": report.get("qcField"),
                "source_url": URL, "source_class": "asos_observation",
                "is_direct_local_bottom_measurement": False,
                "freshness_minutes": limit, "production_weight": 0.0,
                "spatial_scope": "airport_observation; regional_context_for_Eastern_Shore",
                "observation_id": identity, "raw_metar": raw,
                "source_value": str(raw_value) if isinstance(raw_value, float) and not math.isfinite(raw_value) else raw_value,
            })
    return rows, rejected


def current_snapshot(rows, as_of, ingestion_status="complete"):
    """Re-evaluate age and availability at consumption, including offline replay."""
    stations = {}
    limit = freshness_limit()
    for station in STATIONS:
        values = {}
        for field, (parameter, unit, _, _) in FIELDS.items():
            row = next((r for r in rows if r.get("sensor_id") == station and r.get("parameter") == parameter), {})
            observed, available = utc(row.get("observed_at_utc")), utc(row.get("available_at"))
            age = (as_of - observed).total_seconds() / 60 if observed else None
            reason = row.get("qc_flag", "NO_OBSERVATION")
            state, value = row.get("value_status", "UNKNOWN"), row.get("value")
            if not observed or not available:
                state, value, reason = "UNKNOWN", None, "MISSING_TIMESTAMP_OR_OBSERVATION"
            elif available > as_of or observed > as_of:
                state, value, reason = "UNKNOWN", None, "NOT_AVAILABLE_AT_ISSUE_TIME"
            elif age > limit:
                state, value, reason = "UNKNOWN", None, "STALE"
            elif ingestion_status != "complete":
                state, value, reason = "UNKNOWN", None, "INGESTION_UNAVAILABLE"
            values[parameter] = {**row, "value": value, "value_status": state,
                                 "unit": unit, "age_minutes": round(age, 3) if age is not None else None,
                                 "admission_reason": reason, "freshness_minutes": limit}
        known = sum(v["value_status"] in ("KNOWN", "TRACE") for v in values.values())
        stations[station] = {"status": "PARTIAL" if 0 < known < len(values) else ("KNOWN" if known else "UNKNOWN"), "parameters": values}
    return {"schema_version": "1.0", "evaluated_at_utc": as_of.isoformat(),
            "source_class": "asos_observation", "source_url": URL,
            "ingestion_status": ingestion_status, "freshness_minutes": limit,
            "forecast_weights_changed": False, "production_weight": 0.0,
            "stations": stations}


def load_current(directory, as_of):
    """Only matching, successfully published manifest/data pairs may be consumed."""
    try:
        manifest = json.loads((directory / MANIFEST).read_text())
        payload = (directory / NORMALIZED).read_bytes()
        if not isinstance(manifest, dict):
            raise ValueError("Invalid manifest")
        if hashlib.sha256(payload).hexdigest() != manifest.get("normalized_sha256"):
            raise ValueError("Normalized data/manifest mismatch")
        rows = json.loads(payload)
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("Invalid normalized rows")
        return current_snapshot(rows, as_of, manifest["status"])
    except (OSError, ValueError, KeyError, TypeError):
        return current_snapshot([], as_of, "unavailable")


def fetch():
    request = urllib.request.Request(URL, headers={
        "User-Agent": "jubilee-camera-feed/1.0 (github.com/bentsmith4/jubilee-camera-feed)",
        "Accept": "application/json",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read(2_000_001)
                if response.status == 204:
                    return b"[]"
            if len(payload) > 2_000_000:
                raise ValueError("AWC response exceeded 2 MB bound")
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def write_json(path, value):
    payload = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return hashlib.sha256(payload).hexdigest()


def ingest(directory=HERE, fetcher=fetch, clock=lambda: datetime.now(timezone.utc)):
    directory.mkdir(parents=True, exist_ok=True)
    try:
        previous = json.loads((directory / NORMALIZED).read_text())
    except (OSError, ValueError):
        previous = []
    if not isinstance(previous, list):
        previous = []
    started = clock()
    manifest = {"schema_version": "1.0", "started_at_utc": started.isoformat(),
                "source_url": URL, "source_class": "asos_observation",
                "status": "unavailable", "production_action": "NO_CHANGE"}
    # Invalidate the previous run before any network operation. A failed fetch
    # must not leave yesterday's output masquerading as this run's weather.
    manifest["normalized_sha256"] = write_json(directory / NORMALIZED, [])
    write_json(directory / MANIFEST, manifest)
    write_json(directory / SNAPSHOT, current_snapshot([], started, "unavailable"))
    rows = []
    stage = "fetch"
    try:
        payload = fetcher()
        retrieved = clock()  # after response completion, never before the request
        stage = "archive_and_parse"
        manifest["retrieved_at_utc"] = retrieved.isoformat()
        digest = hashlib.sha256(payload).hexdigest()
        archive = directory / "public_archive" / "asos" / (digest + ".json.gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(gzip.compress(payload, mtime=0))
        manifest.update(raw_sha256=digest, raw_path=str(archive.relative_to(directory)))
        rows, rejected = normalize(json.loads(payload), retrieved, previous)
        manifest.update(status="complete", rejected_reports=rejected)
    except urllib.error.HTTPError as exc:
        manifest.update(status="failed" if exc.code in (400, 404, 422) else "unavailable",
                        error_type=type(exc).__name__, http_status=exc.code)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        manifest.update(status="unavailable" if stage == "fetch" else "failed", error_type=type(exc).__name__)
    except (ValueError, TypeError) as exc:
        manifest.update(status="failed", error_type=type(exc).__name__)
    finished = clock()
    manifest.update(finished_at_utc=finished.isoformat(), normalized_rows=len(rows))
    manifest["normalized_sha256"] = write_json(directory / NORMALIZED, rows)
    write_json(directory / MANIFEST, manifest)
    snapshot = current_snapshot(rows, finished, manifest["status"])
    write_json(directory / SNAPSHOT, snapshot)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=HERE)
    parser.add_argument("--snapshot-only", action="store_true", help="Recheck cached observations at issue time without fetching")
    parser.add_argument("--as-of", help="Offset-aware issue time; allowed only with --snapshot-only")
    args = parser.parse_args()
    if args.as_of and (not args.snapshot_only or utc(args.as_of) is None):
        parser.error("--as-of requires --snapshot-only and an offset-aware ISO timestamp")
    if args.snapshot_only:
        as_of = utc(args.as_of) if args.as_of else datetime.now(timezone.utc)
        print(json.dumps(load_current(args.out_dir, as_of), indent=2))
    else:
        manifest = ingest(args.out_dir)
        print(json.dumps(manifest, indent=2))
        if manifest["status"] == "failed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()

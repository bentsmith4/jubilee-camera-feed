#!/usr/bin/env python3
"""Bounded NOAA 8735180 measured water level, for zero-weight bay-mouth context.

This is not Point Clear water level, astronomical tide prediction, current, or
bottom hydrography. Consumers must use load_current at their actual issue time;
a stored snapshot is an audit of its evaluation time, never a freshness grant.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_ID = "noaa_coops_8735180_dauphin_island"
STATION = "8735180"
SOURCE_CLASS = "noaa_observed_water_level"
BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
METADATA_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/8735180.json"
QC_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html"
MANIFEST = "noaa_water_level_manifest.json"
NORMALIZED = "noaa_water_level_normalized.json"
SNAPSHOT = "current_noaa_water_level.json"
HOURS = 6
MAX_BYTES = 2_000_000
MAX_ROWS = 100  # Six-minute observations in a six-hour request: normally <=61.
CONTRACT = {"source_id": SOURCE_ID, "station_id": STATION,
            "source_class": SOURCE_CLASS, "product": "water_level",
            "datum": "MLLW", "units": "metric", "time_zone": "gmt"}


def utc(value):
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
    except (ValueError, TypeError, OverflowError):
        return None


def finite_json_number(value):
    """Reject nonstandard constants and float overflow before retaining fields."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("NOAA JSON contains a non-finite number")
    return parsed


def freshness_limit():
    return json.loads((HERE / "sensor_contract.json").read_text())["freshness_minutes"]["water_level"]


def require_utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An offset-aware evaluation/retrieval time is required")
    return value.astimezone(timezone.utc)


def valid_source_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return False
    query = urllib.parse.parse_qs(parsed.query)
    return (parsed.scheme == "https" and parsed.netloc == "api.tidesandcurrents.noaa.gov"
            and parsed.path == "/api/prod/datagetter" and not parsed.fragment
            and all(query.get(k) == [v] for k, v in {
                "station": STATION, "product": "water_level", "datum": "MLLW",
                "units": "metric", "time_zone": "gmt", "format": "json"}.items()))


def request_url(at):
    end = require_utc(at).replace(second=0, microsecond=0)
    return BASE_URL + "?" + urllib.parse.urlencode({
        "begin_date": (end - timedelta(hours=HOURS)).strftime("%Y%m%d %H:%M"),
        "end_date": end.strftime("%Y%m%d %H:%M"), "station": STATION,
        "product": "water_level", "datum": "MLLW", "time_zone": "gmt",
        "units": "metric", "format": "json", "application": "jubilee-camera-feed"})


def source_time(value):
    # The request explicitly selects GMT. Never interpret a provider-local time.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def source_qc(report):
    """Preserve O/F/R/L preliminary counts versus I/F/R/T verified flags."""
    quality, flags = report.get("q"), report.get("f")
    problems = []
    parsed = None
    if quality not in ("p", "v"):
        problems.append("UNKNOWN_SOURCE_QUALITY")
    if isinstance(flags, str) and re.fullmatch(r"\d+,\d+,\d+,\d+", flags):
        parsed = [int(x) for x in flags.split(",")]
    if parsed is None or any(x not in (0, 1) for x in parsed[1:]) or (quality == "v" and parsed[0] not in (0, 1)):
        problems.append("INVALID_SOURCE_FLAGS")
    else:
        # Preliminary O is a count, not a binary failure or an inferred value.
        if quality == "v" and parsed[0]:
            problems.append("SOURCE_INFERRED_HEIGHT")
        for index, label in ((1, "FLAT"), (2, "RATE"), (3, "HEIGHT_LIMIT")):
            if parsed[index]:
                problems.append("SOURCE_" + label + "_FLAG")
    sigma = number(report.get("s"))
    if sigma is None or sigma < 0:
        problems.append("INVALID_OR_MISSING_SIGMA")
    return problems, parsed, sigma


def normalize(payload, retrieved_at, url, previous=()):
    retrieved_at = require_utc(retrieved_at)
    if not valid_source_url(url):
        raise ValueError("Unexpected NOAA request product, station, units, datum or clock")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("NOAA water-level response requires a data array")
    metadata = payload.get("metadata", {})
    if (not isinstance(metadata, dict) or metadata.get("id") != STATION
            or not isinstance(metadata.get("name"), str)
            or metadata["name"].strip().lower() != "dauphin island"
            or number(metadata.get("lat")) is None or number(metadata.get("lon")) is None
            or number(metadata["lat"]) != 30.25
            or number(metadata["lon"]) != -88.075):
        raise ValueError("Unexpected NOAA station identity or geometry")
    if len(payload["data"]) > MAX_ROWS or any(not isinstance(r, dict) for r in payload["data"]):
        raise ValueError("Unbounded or malformed NOAA observation rows")
    old = {r.get("observation_id"): r for r in previous if isinstance(r, dict)}
    rows, rejected = [], []
    timestamps = {}
    for report in payload["data"]:
        observed = source_time(report.get("t"))
        if observed is None:
            rejected.append({"reason": "INVALID_OBSERVATION_TIME", "source_time": report.get("t")})
            continue
        identity = hashlib.sha256(json.dumps({**CONTRACT, "report": report}, sort_keys=True).encode()).hexdigest()
        if identity in timestamps.setdefault(observed, set()):
            continue
        timestamps[observed].add(identity)
        flags, parsed, sigma = source_qc(report)
        value = number(report.get("v"))
        if value is None:
            flags.append("INVALID_OR_MISSING_VALUE")
        if observed > retrieved_at:
            flags.append("FUTURE_OBSERVATION")
        available = retrieved_at
        prior = utc(old.get(identity, {}).get("available_at"))
        if prior and observed <= prior <= retrieved_at:
            available = prior
        age = (retrieved_at - observed).total_seconds() / 60
        rows.append({
            "sensor_id": STATION, "station_name": "Dauphin Island", "latitude": 30.25, "longitude": -88.075,
            "source_id": SOURCE_ID, "parameter": "water_level", "value": None if flags else value,
            "unit": "m", "vertical_reference": "MLLW", "depth_m": None,
            "product": "water_level", "value_status": "UNKNOWN" if flags else "KNOWN",
            "observed_at_utc": observed.isoformat(), "received_at_utc": None,
            "available_at": available.isoformat(), "ingested_at": retrieved_at.isoformat(),
            "availability_basis": "first_successful_local_retrieval; source receipt time not provided",
            "source_qc_level": report.get("q"),
            "source_qc_description": {"p": "preliminary", "v": "verified"}.get(report.get("q"), "unknown"),
            "source_flags": report.get("f"),
            "source_flag_names": ["outlier_sample_count" if report.get("q") == "p" else "inferred", "flat", "rate", "height_limit"],
            "source_flag_values": parsed, "source_sigma_m": sigma,
            "source_value": report.get("v"), "qc_flag": "|".join(sorted(flags)) if flags else "SOURCE_QC_ACCEPTED",
            "freshness_at_retrieval": "FUTURE" if age < 0 else ("STALE" if age > freshness_limit() else "FRESH"),
            "freshness_minutes": freshness_limit(), "source_url": url, "source_class": SOURCE_CLASS,
            "is_direct_local_bottom_measurement": False, "production_weight": 0.0,
            "spatial_scope": "Dauphin Island bay-mouth observation; regional context for Eastern Shore",
            "independence_group": "noaa_coops_8735180", "observation_id": identity,
        })
    for row in rows:
        if len(timestamps[utc(row["observed_at_utc"])]) > 1:
            row.update(value=None, value_status="UNKNOWN", qc_flag="CONFLICTING_DUPLICATE_TIMESTAMP")
    return sorted(rows, key=lambda r: (r["observed_at_utc"], r["observation_id"])), rejected


def current_snapshot(rows, as_of, ingestion_status="complete"):
    """Latest source observation wins, even if bad; never backfill an older good row."""
    as_of = require_utc(as_of)
    limit = freshness_limit()
    observed_rows = [r for r in rows if isinstance(r, dict) and utc(r.get("observed_at_utc"))]
    row = max(observed_rows, key=lambda r: (utc(r["observed_at_utc"]), str(r.get("observation_id"))), default={})
    observed, available = utc(row.get("observed_at_utc")), utc(row.get("available_at"))
    ingested = utc(row.get("ingested_at"))
    age = (as_of - observed).total_seconds() / 60 if observed else None
    state, reason, value = "UNKNOWN", "NO_OBSERVATION", None
    freshness = "EMPTY"
    if ingestion_status not in ("complete", "empty"):
        reason, freshness = "INGESTION_UNAVAILABLE", "UNAVAILABLE"
    elif observed:
        if observed > as_of:
            reason, freshness = "FUTURE_OBSERVATION", "FUTURE"
        elif not available or not ingested or not observed <= available <= ingested or available > as_of:
            reason, freshness = "NOT_AVAILABLE_AT_ISSUE_TIME", "UNAVAILABLE"
        elif age > limit:
            reason, freshness = "STALE", "STALE"
        elif (row.get("sensor_id") != STATION or row.get("source_id") != SOURCE_ID
              or row.get("source_class") != SOURCE_CLASS or row.get("product") != "water_level"
              or row.get("unit") != "m" or row.get("vertical_reference") != "MLLW"
              or row.get("latitude") != 30.25 or row.get("longitude") != -88.075
              or not valid_source_url(row.get("source_url"))
              or row.get("production_weight") != 0 or row.get("is_direct_local_bottom_measurement") is not False):
            reason, freshness = "INVALID_SOURCE_CONTRACT", "UNKNOWN"
        else:
            freshness = "FRESH"
            reason = row.get("qc_flag", "MISSING_QC")
            # Recheck source fields independently of cached admission labels.
            problems, _, _ = source_qc({"q": row.get("source_qc_level"), "f": row.get("source_flags"), "s": row.get("source_sigma_m")})
            if (not problems and row.get("value_status") == "KNOWN" and reason == "SOURCE_QC_ACCEPTED"
                    and number(row.get("value")) is not None and number(row.get("source_value")) == row["value"]):
                state, value = "KNOWN", row["value"]
            elif problems:
                reason = "|".join(sorted(problems))
            elif reason == "SOURCE_QC_ACCEPTED":
                reason = "INVALID_NORMALIZED_OBSERVATION"
    return {"schema_version": "1.0", **CONTRACT, "evaluated_at_utc": as_of.isoformat(),
            "ingestion_status": ingestion_status, "value_status": state, "value": value,
            "unit": "m", "vertical_reference": "MLLW", "freshness_status": freshness,
            "age_minutes": round(age, 3) if age is not None else None, "freshness_minutes": limit,
            "admission_reason": reason, "observed_at_utc": row.get("observed_at_utc"),
            "available_at": row.get("available_at"), "source_qc_level": row.get("source_qc_level"),
            "source_flags": row.get("source_flags"), "source_sigma_m": row.get("source_sigma_m"),
            "observation_id": row.get("observation_id"), "production_weight": 0.0,
            "spatial_scope": "Dauphin Island bay mouth; not Point Clear observed water level",
            "is_direct_local_bottom_measurement": False, "forecast_weights_changed": False}


def read_pair(directory):
    manifest = json.loads((directory / MANIFEST).read_text())
    payload = (directory / NORMALIZED).read_bytes()
    if (not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in CONTRACT.items())
            or not valid_source_url(manifest.get("source_url"))
            or manifest.get("status") not in ("complete", "empty", "unavailable", "failed")
            or hashlib.sha256(payload).hexdigest() != manifest.get("normalized_sha256")):
        raise ValueError("NOAA normalized data/manifest contract mismatch")
    rows = json.loads(payload)
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows)
            or manifest.get("normalized_rows") != len(rows) or len(rows) > MAX_ROWS
            or (manifest.get("status") == "complete") != bool(rows)
            or any(r.get("ingested_at") != manifest.get("retrieved_at_utc") for r in rows)):
        raise ValueError("Invalid normalized rows")
    return manifest, rows


def load_current(directory, as_of):
    as_of = require_utc(as_of)
    try:
        manifest, rows = read_pair(Path(directory))
        retrieved = utc(manifest.get("retrieved_at_utc"))
        if not retrieved or retrieved > as_of:
            return current_snapshot([], as_of, "unavailable")
        return current_snapshot(rows, as_of, manifest["status"])
    except (OSError, ValueError, KeyError, TypeError):
        return current_snapshot([], as_of, "unavailable")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "jubilee-camera-feed/1.0", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError("NOAA response exceeded 2 MB bound")
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
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        old_manifest, previous = read_pair(directory)
        if old_manifest.get("status") != "complete":
            previous = []
    except (OSError, ValueError, TypeError, KeyError):
        previous = []
    started = require_utc(clock())
    url = request_url(started)
    manifest = {"schema_version": "1.0", **CONTRACT, "started_at_utc": started.isoformat(),
                "source_url": url, "window_hours": HOURS, "status": "unavailable", "normalized_rows": 0,
                "production_action": "NO_CHANGE", "production_weight": 0.0, "source_qc_reference": QC_URL}
    # Invalidate old current output before network access, including interrupted runs.
    manifest["normalized_sha256"] = write_json(directory / NORMALIZED, [])
    write_json(directory / MANIFEST, manifest)
    write_json(directory / SNAPSHOT, current_snapshot([], started, "unavailable"))
    rows, stage = [], "fetch"
    try:
        payload = fetcher(url)
        retrieved = require_utc(clock())
        if retrieved < started:
            raise ValueError("Retrieval clock moved backward")
        stage = "archive_and_parse"
        if len(payload) > MAX_BYTES:
            raise ValueError("NOAA response exceeded 2 MB bound")
        digest = hashlib.sha256(payload).hexdigest()
        archive = directory / "public_archive" / "coops" / (digest + ".json.gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            if gzip.decompress(archive.read_bytes()) != payload:
                raise ValueError("Existing immutable NOAA raw archive mismatch")
        else:
            archive.write_bytes(gzip.compress(payload, mtime=0))
        manifest.update(retrieved_at_utc=retrieved.isoformat(), raw_sha256=digest,
                        raw_path=str(archive.relative_to(directory)), raw_bytes=len(payload))
        decoded = json.loads(payload, parse_constant=finite_json_number, parse_float=finite_json_number)
        if isinstance(decoded, dict) and "error" in decoded:
            error = decoded["error"]
            message = error.get("message", "") if isinstance(error, dict) else ""
            if isinstance(message, str) and message.strip().lower().startswith("no data was found"):
                manifest.update(status="empty", source_error=message)
            else:
                raise ValueError("NOAA returned an unexpected API error")
        else:
            rows, rejected = normalize(decoded, retrieved, url, previous)
            manifest.update(status="complete" if rows else "empty", rejected_reports=rejected)
            if rejected:
                # A bad timestamp may belong to the newest observation. Do not
                # silently fall back to an older good row when ordering is unknown.
                rows = []
                raise ValueError("NOAA response contains unorderable observation times")
    except urllib.error.HTTPError as exc:
        manifest.update(status="failed" if exc.code in (400, 404, 422) else "unavailable",
                        error_type=type(exc).__name__, http_status=exc.code)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        manifest.update(status="unavailable" if stage == "fetch" else "failed", error_type=type(exc).__name__)
    except (ValueError, TypeError, OverflowError) as exc:
        manifest.update(status="failed", error_type=type(exc).__name__)
    finished = require_utc(clock())
    if finished < (utc(manifest.get("retrieved_at_utc")) or started):
        manifest.update(status="failed", error_type="ClockRegression")
        rows = []
    manifest.update(finished_at_utc=finished.isoformat(), normalized_rows=len(rows),
                    latest_observed_at_utc=max((r["observed_at_utc"] for r in rows), default=None))
    manifest["normalized_sha256"] = write_json(directory / NORMALIZED, rows)
    snapshot = current_snapshot(rows, finished, manifest["status"])
    manifest.update(current_value_status=snapshot["value_status"], current_freshness=snapshot["freshness_status"])
    write_json(directory / MANIFEST, manifest)
    write_json(directory / SNAPSHOT, snapshot)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=HERE)
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--as-of", help="Offset-aware issue time; requires --snapshot-only")
    args = parser.parse_args()
    if args.as_of and (not args.snapshot_only or utc(args.as_of) is None):
        parser.error("--as-of requires --snapshot-only and an offset-aware ISO timestamp")
    if args.snapshot_only:
        print(json.dumps(load_current(args.out_dir, utc(args.as_of) if args.as_of else datetime.now(timezone.utc)), indent=2))
    else:
        manifest = ingest(args.out_dir)
        print(json.dumps(manifest, indent=2))
        if manifest["status"] == "failed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()

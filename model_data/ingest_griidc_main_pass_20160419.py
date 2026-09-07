#!/usr/bin/env python3
"""Ingest the 2016-04-19 Main Pass Mobile Bay CTD survey from GRIIDC ERDDAP.

Historical DIRECT observations only at cast location/depth/time. Raw public
responses are cached immutably by SHA-256; normalized rows are written to the
canonical model_data layer. No production weights are changed.
"""
from __future__ import annotations

import csv, gzip, hashlib, io, json, math, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCH = "https://erddap.griidc.org/erddap/search/index.json"
PREFIX = "R4_x260_000_0055_"
SOURCE_UDI = "R4.x260.000:0055"
SOURCE_DOI = "10.7266/N75X279Z"
AVAILABLE_AT = "2017-07-06T20:47:00+00:00"
ARCHIVE = HERE / "public_archive" / "griidc_main_pass_20160419"
NORMALIZED = HERE / "griidc_main_pass_20160419_normalized.csv"
MANIFEST = HERE / "griidc_main_pass_20160419_manifest.json"
USER_AGENT = "jubilee-research/1.0"

PARAMETERS = {
    "depth": ("depth", "m"),
    "sea_water_temperature": ("water_temperature", "degC"),
    "sea_water_electrical_conductivity": ("conductivity", "uS/cm"),
    "sea_water_salinity": ("salinity", "PSU"),
    "dissolved_oxygen": ("dissolved_oxygen", "mg/L"),
    "oxygen_saturation": ("dissolved_oxygen_percent_saturation", "%"),
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def finite(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def discover_ids():
    url = SEARCH + "?" + urllib.parse.urlencode({"page": 1, "itemsPerPage": 1000, "searchFor": PREFIX.rstrip("_")})
    doc = json.loads(fetch(url))
    cols = doc.get("table", {}).get("columnNames", [])
    ids = []
    for row in doc.get("table", {}).get("rows", []):
        item = dict(zip(cols, row))
        did = str(item.get("Dataset ID") or "")
        if did.startswith(PREFIX):
            ids.append(did)
    return sorted(set(ids)), url


def stable_id(dataset_id, observed_at, lat, lon, scan, parameter):
    raw = "|".join(map(str, [SOURCE_UDI, dataset_id, observed_at, lat, lon, scan, parameter]))
    return hashlib.sha256(raw.encode()).hexdigest()


def main():
    retrieved = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": "1.0", "source_udi": SOURCE_UDI, "doi": SOURCE_DOI,
        "retrieved_at": retrieved, "available_at": AVAILABLE_AT,
        "evidence_class": "DIRECT", "production_action": "NO_CHANGE", "status": "failed"
    }
    rows = []
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    try:
        ids, search_url = discover_ids()
        if len(ids) != 29:
            raise ValueError(f"Expected 29 Main Pass profile datasets; found {len(ids)}")
        raw_hashes = []
        for did in ids:
            url = f"https://erddap.griidc.org/erddap/tabledap/{did}.csv"
            payload = fetch(url)
            digest = hashlib.sha256(payload).hexdigest()
            raw_path = ARCHIVE / f"{digest}.csv.gz"
            if not raw_path.exists():
                raw_path.write_bytes(gzip.compress(payload, mtime=0))
            raw_hashes.append({"dataset_id": did, "sha256": digest, "archive": str(raw_path.relative_to(HERE)), "source_url": url})
            text = payload.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            # ERDDAP CSV has a second units row. Skip it by requiring parseable lat/lon/time.
            for src in reader:
                observed_at = src.get("time")
                lat, lon = finite(src.get("latitude")), finite(src.get("longitude"))
                if not observed_at or lat is None or lon is None or "UTC" == observed_at:
                    continue
                scan = src.get("nscan")
                flag = src.get("flag")
                for source_col, (parameter, unit) in PARAMETERS.items():
                    value = finite(src.get(source_col))
                    if value is None:
                        continue
                    rows.append({
                        "observation_id": stable_id(did, observed_at, lat, lon, scan, parameter),
                        "source_id": "griidc_main_pass_20160419", "source_udi": SOURCE_UDI,
                        "dataset_id": did, "evidence_class": "DIRECT", "parameter": parameter,
                        "value": value, "unit": unit, "depth_m": finite(src.get("depth")),
                        "latitude": lat, "longitude": lon, "observed_at": observed_at,
                        "available_at": AVAILABLE_AT, "ingested_at": retrieved, "source_qc_flag": flag,
                        "production_weight": 0.0,
                    })
        if not rows:
            raise ValueError("No normalized rows produced")
        fields = list(rows[0])
        with NORMALIZED.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
        by_param = {}
        for r in rows: by_param[r["parameter"]] = by_param.get(r["parameter"], 0) + 1
        manifest.update({
            "status": "complete", "discovery_url": search_url, "profile_count": len(ids),
            "normalized_rows": len(rows), "parameter_counts": by_param,
            "raw_objects": raw_hashes, "normalized_csv": NORMALIZED.name,
            "rights": "GRIIDC ERDDAP metadata states these data may be redistributed and used without restriction.",
            "guardrails": [
                "DIRECT only at cast latitude/longitude/depth/time; do not call this Eastern Shore shoreline DO.",
                "Historical calibration source, not a current sensor.",
                "No production weight until leakage-safe held-out incremental value is demonstrated."
            ]
        })
    except Exception as exc:
        manifest.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:1000]})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] != "complete": raise SystemExit(1)

if __name__ == "__main__":
    main()

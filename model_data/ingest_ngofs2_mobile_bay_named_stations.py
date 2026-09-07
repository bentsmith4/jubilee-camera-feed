#!/usr/bin/env python3
"""Extract a compact set of official Mobile Bay NGOFS2 station time series.

This is MODEL guidance, never direct observation. The named points provide a
low-cost bridge between the verified Point Clear extractor and future
shoreline-cell regular-grid extraction. Cell mappings remain explicit proxies
unless the station is actually in the cell.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from netCDF4 import Dataset, chartostring, num2date

HERE = Path(__file__).resolve().parent
BASE = "https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/NOAA/NGOFS2/MODELS"
CYCLE_HOURS = (3, 9, 15, 21)
MAX_FALLBACK_DISTANCE_KM = 10.0

# NOAA/public landmark coordinates. These are public coordinates, not
# private-property coordinates.
TARGETS = [
    {"station_id": "8733502", "label": "Fly Creek", "lat": 30.5428, "lon": -87.9010,
     "cell_roles": ["Montrose:nearby_model_proxy", "Fairhope/Fly Creek/Pier:in_cell_model_point", "Daphne/May Day:southern_proxy"]},
    {"station_id": "8733821", "label": "Point Clear", "lat": 30.486639, "lon": -87.934528,
     "cell_roles": ["Point Clear/Grand Hotel:in_cell_model_point", "Battles Wharf:nearby_model_proxy"]},
    {"station_id": "8732828", "label": "Weeks Bay", "lat": 30.4167, "lon": -87.8250,
     "cell_roles": ["Mullet Point:regional_model_proxy", "Bay mouth:upper_boundary_context"]},
    {"station_id": "8733839", "label": "Meaher State Park", "lat": 30.667167, "lon": -87.936444,
     "cell_roles": ["Daphne/May Day:northern_model_proxy", "Montrose:northern_context"]},
    {"station_id": "8735181", "label": "Dauphin Island Hydro", "lat": 30.251319, "lon": -88.079486,
     "cell_roles": ["Bay mouth:boundary_model_point", "shelf:near_mouth_context"]},
]


def normalize_lon(value: float) -> float:
    return ((float(value) + 180.0) % 360.0) - 180.0


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(normalize_lon(float(lon2) - float(lon1)))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def cycle_candidates(now: datetime, count: int = 8):
    cutoff = now.astimezone(timezone.utc) - timedelta(minutes=90)
    out = []
    for back in range(3):
        d = cutoff.date() - timedelta(days=back)
        for hour in reversed(CYCLE_HOURS):
            candidate = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
            if candidate <= cutoff:
                out.append(candidate)
                if len(out) >= count:
                    return out
    return out


def station_url(cycle: datetime, cast: str):
    date = cycle.strftime("%Y%m%d")
    return f"{BASE}/{cycle:%Y/%m/%d}/ngofs2.t{cycle:%H}z.{date}.stations.{cast}.nc"


def decode_names(variable):
    raw = variable[:]
    if getattr(raw.dtype, "kind", None) == "S":
        if raw.ndim == 1:
            return [bytes(x).decode("utf-8", errors="replace").replace("\x00", "").strip() for x in raw]
        values = chartostring(raw).tolist()
        if isinstance(values, str):
            values = [values]
        return [str(x).replace("\x00", "").strip() for x in values]
    values = raw.tolist()
    if not isinstance(values, list):
        values = [values]
    return [str(x).replace("\x00", "").strip() for x in values]


def as_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def choose_vertical_indices(sigmas):
    values = [float(x) for x in sigmas]
    return max(range(len(values)), key=lambda i: values[i]), min(range(len(values)), key=lambda i: values[i])


def resolve_exact(target, names):
    """Resolve only a true station-id/name match; never use proximity here."""
    folded = [n.casefold().replace("+", " ") for n in names]
    station_id = target["station_id"].casefold()
    label = target["label"].casefold()
    id_matches = [i for i, n in enumerate(folded) if station_id in n]
    if len(id_matches) == 1:
        return id_matches[0], "station_id"
    label_matches = [i for i, n in enumerate(folded) if label in n]
    if len(label_matches) == 1:
        return label_matches[0], "label"
    return None


def resolve_proxy(target, lats, lons, excluded_indices=frozenset()):
    """Resolve nearest unused model station without stealing an exact target."""
    distances = []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        if i in excluded_indices:
            continue
        latv, lonv = as_float(lat), as_float(lon)
        if latv is None or lonv is None:
            continue
        d = haversine_km(target["lat"], target["lon"], latv, normalize_lon(lonv))
        distances.append((d, i))
    if not distances:
        raise ValueError(f"No finite unused station coordinates for {target['label']}")
    distance, idx = min(distances)
    if distance > MAX_FALLBACK_DISTANCE_KM:
        raise ValueError(f"Nearest unused model station for {target['label']} is {distance:.2f} km away")
    return idx, "nearest_verified_coordinate"


def open_latest(cast, now):
    failures = []
    for cycle in cycle_candidates(now):
        url = station_url(cycle, cast)
        try:
            return Dataset(url, mode="r"), url, cycle, failures
        except Exception as exc:
            failures.append({"url": url, "error_type": type(exc).__name__})
    raise RuntimeError(f"No recent NGOFS2 {cast} station file opened: {failures}")


def extract(ds, url, cycle, retrieved_at):
    required = {"name_station", "lon", "lat", "h", "siglay", "time", "u", "v", "temp", "salinity", "zeta"}
    missing = sorted(required - set(ds.variables))
    if missing:
        raise ValueError(f"Missing NGOFS2 variables: {missing}")
    names = decode_names(ds.variables["name_station"])
    lats = ds.variables["lat"][:]
    lons = ds.variables["lon"][:]
    tvar = ds.variables["time"]
    times = num2date(tvar[:], units=tvar.units, calendar=getattr(tvar, "calendar", "standard"), only_use_cftime_datetimes=False)
    rows, station_meta, unresolved = [], [], []

    # Reserve all exact station/name matches before assigning any proximity
    # proxy. This prevents a nearby proxy target (historically Fly Creek) from
    # consuming the Point Clear station and making Point Clear disappear.
    exact = {}
    reserved_exact = set()
    for target in TARGETS:
        resolved = resolve_exact(target, names)
        if resolved is None:
            continue
        idx, basis = resolved
        if idx in reserved_exact:
            unresolved.append({
                "station_id": target["station_id"], "label": target["label"],
                "error_type": "duplicate_exact_model_station_resolution",
                "error": f"exact match resolved index {idx} already reserved"
            })
            continue
        exact[target["station_id"]] = (idx, basis)
        reserved_exact.add(idx)

    used_indices = set()
    for target in TARGETS:
        if target["station_id"] in exact:
            idx, basis = exact[target["station_id"]]
        else:
            try:
                idx, basis = resolve_proxy(target, lats, lons, reserved_exact | used_indices)
            except Exception as exc:
                unresolved.append({"station_id": target["station_id"], "label": target["label"], "error_type": type(exc).__name__, "error": str(exc)})
                continue
        if idx in used_indices:
            unresolved.append({"station_id": target["station_id"], "label": target["label"], "error_type": "duplicate_model_station_resolution", "error": f"resolved index {idx} already assigned"})
            continue
        used_indices.add(idx)
        source_lon = as_float(lons[idx]); lon = normalize_lon(source_lon); lat = as_float(lats[idx])
        distance = haversine_km(target["lat"], target["lon"], lat, lon)
        sigmas = ds.variables["siglay"][:, idx]
        surface_i, bottom_i = choose_vertical_indices(sigmas)
        station_meta.append({
            "target_station_id": target["station_id"], "target_label": target["label"], "model_station_name": names[idx],
            "station_index": idx, "resolution_basis": basis, "distance_to_official_coordinate_km": round(distance, 4),
            "target_lat": target["lat"], "target_lon": target["lon"],
            "lat": lat, "lon": lon, "source_lon": source_lon, "bathymetry_m": as_float(ds.variables["h"][idx]),
            "surface_sigma_index": surface_i, "bottom_sigma_index": bottom_i, "cell_roles": target["cell_roles"],
            "proxy_distance_warning": basis == "nearest_verified_coordinate" and distance > 2.0,
        })
        for ti, valid in enumerate(times):
            valid = valid.replace(tzinfo=timezone.utc) if valid.tzinfo is None else valid.astimezone(timezone.utc)
            zeta = as_float(ds.variables["zeta"][ti, idx])
            for role, layer_i in (("surface", surface_i), ("bottom", bottom_i)):
                vals = {
                    "eastward_current": (as_float(ds.variables["u"][ti, layer_i, idx]), "m/s"),
                    "northward_current": (as_float(ds.variables["v"][ti, layer_i, idx]), "m/s"),
                    "water_temperature": (as_float(ds.variables["temp"][ti, layer_i, idx]), "degC"),
                    "salinity": (as_float(ds.variables["salinity"][ti, layer_i, idx]), "1e-3")
                }
                for parameter, (value, unit) in vals.items():
                    if value is None:
                        continue
                    rows.append({
                        "source_id": "noaa_ngofs2_mobile_bay_named_station", "evidence_class": "MODEL",
                        "target_station_id": target["station_id"], "target_label": target["label"], "model_station_name": names[idx],
                        "resolution_basis": basis, "distance_to_target_km": round(distance, 4),
                        "lat": lat, "lon": lon, "vertical_role": role, "sigma_layer_index": layer_i,
                        "parameter": parameter, "value": value, "unit": unit, "valid_at": valid.isoformat(),
                        "model_initialized_at": cycle.isoformat(), "available_at": retrieved_at.isoformat(), "ingested_at": retrieved_at.isoformat(),
                        "source_url": url, "production_weight": 0.0
                    })
            if zeta is not None:
                rows.append({
                    "source_id": "noaa_ngofs2_mobile_bay_named_station", "evidence_class": "MODEL",
                    "target_station_id": target["station_id"], "target_label": target["label"], "model_station_name": names[idx],
                    "resolution_basis": basis, "distance_to_target_km": round(distance, 4),
                    "lat": lat, "lon": lon, "vertical_role": "surface", "sigma_layer_index": None,
                    "parameter": "water_surface_elevation", "value": zeta, "unit": "m", "valid_at": valid.isoformat(),
                    "model_initialized_at": cycle.isoformat(), "available_at": retrieved_at.isoformat(), "ingested_at": retrieved_at.isoformat(),
                    "source_url": url, "production_weight": 0.0
                })
    return rows, station_meta, unresolved


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cast", choices=["nowcast", "forecast"], default="nowcast")
    args = p.parse_args()
    retrieved = datetime.now(timezone.utc)
    manifest = {"schema_version": "1.1", "cast": args.cast, "retrieved_at": retrieved.isoformat(), "status": "failed", "evidence_class": "MODEL", "production_action": "NO_CHANGE"}
    try:
        ds, url, cycle, failed = open_latest(args.cast, retrieved)
        try:
            rows, stations, unresolved = extract(ds, url, cycle, retrieved)
        finally:
            ds.close()
        if not rows:
            raise ValueError("No NGOFS2 named-station rows extracted")
        payload = json.dumps({"source_url": url, "cycle": cycle.isoformat(), "cast": args.cast, "stations": stations, "rows": rows}, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(payload).hexdigest()
        archive = HERE / "public_archive" / "ngofs2_named_station_subset" / f"{digest}.json.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(gzip.compress(payload, mtime=0))
        csv_path = HERE / f"ngofs2_mobile_bay_named_stations_{args.cast}_normalized.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
        manifest.update({
            "status": "complete", "source_url": url, "model_initialized_at": cycle.isoformat(), "failed_newer_attempts": failed,
            "station_count": len(stations), "stations": stations, "unresolved_targets": unresolved, "normalized_rows": len(rows),
            "subset_sha256": digest, "subset_archive": str(archive.relative_to(HERE)), "normalized_csv": str(csv_path.relative_to(HERE)),
            "guardrails": [
                "All values are MODEL guidance, not observations.",
                "Exact station-ID/name matches are reserved before proximity proxies are assigned.",
                "Cell roles are explicit named-point proxies until shoreline regular-grid extraction is validated.",
                "No station negative or model state is a Jubilee non-event label.",
                "No production weight without held-out incremental value.",
                "Public station coordinates only; no private-property coordinates are stored."
            ]
        })
    except Exception as exc:
        manifest.update({"error_type": type(exc).__name__, "error": str(exc)})
    out = HERE / f"ngofs2_mobile_bay_named_stations_{args.cast}_manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

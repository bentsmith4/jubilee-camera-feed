#!/usr/bin/env python3
"""Extract NGOFS2 regular-grid guidance along public Eastern Shore transects.

This removes dependence on a single named station for multiple shoreline cells.
It uses public landmark/locality anchors, walks offshore along an explicit
provisional normal, selects nearby wet model nodes, and preserves exact grid
coordinates/bathymetry. Output remains MODEL guidance with zero production
weight until held-out validation demonstrates incremental value.
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

import numpy as np
from netCDF4 import Dataset, num2date

HERE = Path(__file__).resolve().parent
TARGET_FILE = HERE / "ngofs2_target_cells.json"
BASE = "https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/NOAA/NGOFS2/MODELS"
CYCLE_HOURS = (3, 9, 15, 21)
FORECAST_LEADS = (0, 1, 2, 3, 4, 5, 6, 9, 12)
NOWCAST_LEADS = (1, 2, 3, 4, 5, 6)
MAX_NODE_DISTANCE_KM = 1.5
FILL_CUTOFF = -9000.0


def normalize_lon(value):
    return ((float(value) + 180.0) % 360.0) - 180.0


def cycle_candidates(now: datetime, count: int = 8):
    cutoff = now.astimezone(timezone.utc) - timedelta(minutes=90)
    out = []
    for back in range(3):
        day = cutoff.date() - timedelta(days=back)
        for hour in reversed(CYCLE_HOURS):
            candidate = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
            if candidate <= cutoff:
                out.append(candidate)
                if len(out) >= count:
                    return out
    return out


def regulargrid_url(cycle: datetime, cast: str, lead: int):
    token = "f" if cast == "forecast" else "n"
    date = cycle.strftime("%Y%m%d")
    return f"{BASE}/{cycle:%Y/%m/%d}/ngofs2.t{cycle:%H}z.{date}.regulargrid.{token}{lead:03d}.nc"


def destination(lat, lon, bearing_deg, distance_km):
    """Small-distance spherical destination point."""
    r = 6371.0088
    b = math.radians(float(bearing_deg))
    p1 = math.radians(float(lat))
    l1 = math.radians(float(lon))
    d = float(distance_km) / r
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), normalize_lon(math.degrees(l2))


def distance_grid_km(lat_grid, lon_grid, lat, lon):
    """Fast local equirectangular distance adequate for node selection."""
    dy = (np.asarray(lat_grid, dtype=float) - float(lat)) * 111.195
    dx = (np.vectorize(normalize_lon)(np.asarray(lon_grid, dtype=float)) - float(lon)) * 111.195 * math.cos(math.radians(float(lat)))
    return np.hypot(dx, dy)


def safe_array(variable, key):
    arr = np.ma.asarray(variable[key])
    return np.asarray(arr.filled(np.nan), dtype=float)


def finite_value(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > FILL_CUTOFF else None


def shoreward_component(u, v, bearing_deg):
    if u is None or v is None:
        return None
    theta = math.radians(float(bearing_deg))
    # Bearing is degrees clockwise from true north.
    return float(u) * math.sin(theta) + float(v) * math.cos(theta)


def load_targets():
    doc = json.loads(TARGET_FILE.read_text(encoding="utf-8"))
    offsets = doc.get("default_offshore_offsets_km", [0.25, 0.75, 1.5, 3.0])
    rows = []
    for target in doc.get("targets", []):
        if target.get("lat") is None or target.get("lon") is None:
            continue
        row = dict(target)
        row["offshore_offsets_km"] = row.get("offshore_offsets_km", offsets)
        rows.append(row)
    return rows


def open_reference(cast, now):
    """Open a reference file from the newest usable cycle."""
    probe_lead = 0 if cast == "forecast" else 3
    failures = []
    for cycle in cycle_candidates(now):
        url = regulargrid_url(cycle, cast, probe_lead)
        try:
            return Dataset(url, "r"), cycle, url, failures
        except Exception as exc:
            failures.append({"url": url, "error_type": type(exc).__name__})
    raise RuntimeError(f"No recent NGOFS2 regular-grid {cast} reference file opened: {failures}")


def select_nodes(ds, targets):
    required = {"Latitude", "Longitude", "h", "mask", "Depth"}
    missing = sorted(required - set(ds.variables))
    if missing:
        raise ValueError(f"Regular-grid reference missing variables: {missing}")
    lat = safe_array(ds.variables["Latitude"], slice(None))
    lon_raw = safe_array(ds.variables["Longitude"], slice(None))
    lon = ((lon_raw + 180.0) % 360.0) - 180.0
    h = safe_array(ds.variables["h"], slice(None))
    mask = safe_array(ds.variables["mask"], slice(None))
    wet = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(h) & (h > 0) & np.isfinite(mask) & (mask > 0)
    nodes = []
    for target in targets:
        used = set()
        for offset in target["offshore_offsets_km"]:
            tlat, tlon = destination(target["lat"], target["lon"], target["offshore_bearing_deg_true"], offset)
            d = np.hypot((lat - tlat) * 111.195, (lon - tlon) * 111.195 * math.cos(math.radians(tlat)))
            d = np.where(wet, d, np.inf)
            flat_order = np.argsort(d, axis=None)
            picked = None
            for flat in flat_order[:1000]:
                yi, xi = np.unravel_index(int(flat), d.shape)
                if (yi, xi) not in used:
                    picked = (yi, xi, float(d[yi, xi]))
                    break
            if picked is None:
                raise ValueError(f"No unique wet NGOFS2 node found for {target['cell']} offset {offset}")
            yi, xi, node_distance = picked
            if node_distance > MAX_NODE_DISTANCE_KM:
                raise ValueError(f"Nearest wet NGOFS2 node for {target['cell']} offset {offset} is {node_distance:.2f} km away")
            used.add((yi, xi))
            nodes.append({
                "cell": target["cell"],
                "target_name": target["target_name"],
                "coordinate_basis": target["coordinate_basis"],
                "anchor_lat": target["lat"],
                "anchor_lon": target["lon"],
                "shoreward_bearing_deg_true": target["shoreward_bearing_deg_true"],
                "offshore_bearing_deg_true": target["offshore_bearing_deg_true"],
                "bearing_status": target.get("bearing_status"),
                "requested_offshore_offset_km": float(offset),
                "requested_target_lat": tlat,
                "requested_target_lon": tlon,
                "grid_y": int(yi),
                "grid_x": int(xi),
                "grid_lat": float(lat[yi, xi]),
                "grid_lon": float(lon[yi, xi]),
                "bathymetry_m": float(h[yi, xi]),
                "distance_to_requested_target_km": node_distance,
            })
    return nodes


def parse_time(ds):
    tvar = ds.variables["time"]
    raw = num2date(tvar[:], units=tvar.units, calendar=getattr(tvar, "calendar", "standard"), only_use_cftime_datetimes=False)
    dt = raw[0]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_one_file(ds, source_url, cycle, cast, lead, nodes, retrieved_at):
    required = {"Depth", "time", "zeta", "u_eastward", "v_northward", "temp", "salt"}
    missing = sorted(required - set(ds.variables))
    if missing:
        raise ValueError(f"Regular-grid file missing variables: {missing}")
    depths = safe_array(ds.variables["Depth"], slice(None)).reshape(-1)
    valid_at = parse_time(ds)
    raw_records = []
    normalized = []
    features = []

    # One bounding rectangle reduces OPeNDAP round trips compared with reading
    # 24 arbitrary point profiles independently.
    ys = [n["grid_y"] for n in nodes]
    xs = [n["grid_x"] for n in nodes]
    y0, y1 = min(ys), max(ys)
    x0, x1 = min(xs), max(xs)
    ubox = safe_array(ds.variables["u_eastward"], (0, slice(None), slice(y0, y1 + 1), slice(x0, x1 + 1)))
    vbox = safe_array(ds.variables["v_northward"], (0, slice(None), slice(y0, y1 + 1), slice(x0, x1 + 1)))
    tbox = safe_array(ds.variables["temp"], (0, slice(None), slice(y0, y1 + 1), slice(x0, x1 + 1)))
    sbox = safe_array(ds.variables["salt"], (0, slice(None), slice(y0, y1 + 1), slice(x0, x1 + 1)))
    zbox = safe_array(ds.variables["zeta"], (0, slice(y0, y1 + 1), slice(x0, x1 + 1)))

    for node in nodes:
        yy, xx = node["grid_y"] - y0, node["grid_x"] - x0
        u = ubox[:, yy, xx]
        v = vbox[:, yy, xx]
        temp = tbox[:, yy, xx]
        salt = sbox[:, yy, xx]
        finite = np.isfinite(u) & np.isfinite(v) & np.isfinite(temp) & np.isfinite(salt) & (u > FILL_CUTOFF) & (v > FILL_CUTOFF) & (temp > FILL_CUTOFF) & (salt > FILL_CUTOFF)
        valid_idx = np.where(finite)[0]
        if not len(valid_idx):
            continue
        surface_i, bottom_i = int(valid_idx[0]), int(valid_idx[-1])
        zeta = finite_value(zbox[yy, xx])
        raw_node = {
            "cast": cast, "lead_hour": int(lead), "source_url": source_url, "model_initialized_at": cycle.isoformat(),
            "valid_at": valid_at.isoformat(), "cell": node["cell"], "grid_y": node["grid_y"], "grid_x": node["grid_x"],
            "grid_lat": node["grid_lat"], "grid_lon": node["grid_lon"], "bathymetry_m": node["bathymetry_m"],
            "requested_offshore_offset_km": node["requested_offshore_offset_km"], "zeta_m": zeta,
            "surface": {}, "bottom": {}
        }
        role_values = {}
        for role, idx in (("surface", surface_i), ("bottom", bottom_i)):
            vals = {
                "eastward_current": finite_value(u[idx]),
                "northward_current": finite_value(v[idx]),
                "water_temperature": finite_value(temp[idx]),
                "salinity": finite_value(salt[idx]),
            }
            vals["shoreward_current"] = shoreward_component(vals["eastward_current"], vals["northward_current"], node["shoreward_bearing_deg_true"])
            raw_node[role] = {"standard_depth_m": finite_value(depths[idx]), **vals}
            role_values[role] = vals
            for parameter, unit in (("eastward_current", "m/s"), ("northward_current", "m/s"), ("shoreward_current", "m/s"), ("water_temperature", "degC"), ("salinity", "PSU")):
                value = vals.get(parameter)
                if value is None:
                    continue
                normalized.append({
                    "source_id": "noaa_ngofs2_mobile_bay_regulargrid",
                    "source_class": "MODEL",
                    "station_or_camera_id": f"ngofs2_grid_{node['grid_y']}_{node['grid_x']}",
                    "independence_group": "noaa_ngofs2_mobile_bay_model",
                    "shoreline_cell": node["cell"],
                    "requested_offshore_offset_km": node["requested_offshore_offset_km"],
                    "grid_lat": node["grid_lat"], "grid_lon": node["grid_lon"], "bathymetry_m": node["bathymetry_m"],
                    "variable_or_evidence_type": parameter, "value_or_status": value, "units": unit,
                    "vertical_role": role, "depth": finite_value(depths[idx]), "vertical_reference": "standard_depth_positive_down",
                    "datum": "model_grid_or_not_applicable", "qc_status": "MODEL_WET_GRID_NODE",
                    "observed_at": None, "valid_at": valid_at.isoformat(), "available_at": retrieved_at.isoformat(), "ingested_at": retrieved_at.isoformat(),
                    "timezone": "UTC", "model_initialized_at": cycle.isoformat(), "cast": cast, "lead_hour": int(lead),
                    "source_url": source_url, "production_weight": 0.0,
                })
        if zeta is not None:
            normalized.append({
                "source_id": "noaa_ngofs2_mobile_bay_regulargrid", "source_class": "MODEL",
                "station_or_camera_id": f"ngofs2_grid_{node['grid_y']}_{node['grid_x']}",
                "independence_group": "noaa_ngofs2_mobile_bay_model", "shoreline_cell": node["cell"],
                "requested_offshore_offset_km": node["requested_offshore_offset_km"],
                "grid_lat": node["grid_lat"], "grid_lon": node["grid_lon"], "bathymetry_m": node["bathymetry_m"],
                "variable_or_evidence_type": "water_surface_elevation", "value_or_status": zeta, "units": "m",
                "vertical_role": "surface", "depth": 0.0, "vertical_reference": "surface", "datum": "model_mean_sea_level",
                "qc_status": "MODEL_WET_GRID_NODE", "observed_at": None, "valid_at": valid_at.isoformat(),
                "available_at": retrieved_at.isoformat(), "ingested_at": retrieved_at.isoformat(), "timezone": "UTC",
                "model_initialized_at": cycle.isoformat(), "cast": cast, "lead_hour": int(lead), "source_url": source_url, "production_weight": 0.0,
            })
        sv, bv = role_values.get("surface", {}), role_values.get("bottom", {})
        for name, value, unit in (
            ("surface_minus_bottom_salinity_psu", None if sv.get("salinity") is None or bv.get("salinity") is None else sv["salinity"] - bv["salinity"], "PSU"),
            ("surface_minus_bottom_temperature_C", None if sv.get("water_temperature") is None or bv.get("water_temperature") is None else sv["water_temperature"] - bv["water_temperature"], "degC"),
            ("bottom_minus_surface_shoreward_current_m_s", None if sv.get("shoreward_current") is None or bv.get("shoreward_current") is None else bv["shoreward_current"] - sv["shoreward_current"], "m/s"),
        ):
            if value is not None:
                features.append({
                    "feature_id": name, "feature_version": "ngofs2_regulargrid_v1", "target_time": valid_at.isoformat(),
                    "available_by_target_time": False, "shoreline_cell": node["cell"], "requested_offshore_offset_km": node["requested_offshore_offset_km"],
                    "grid_lat": node["grid_lat"], "grid_lon": node["grid_lon"], "value": value, "units": unit,
                    "missingness_reason": None, "source_observation_ids": "same_grid_node_time_surface_bottom",
                    "transform_code_hash": "SELF_FILE_HASH_AT_COMMIT", "source_class": "MODEL_DERIVED", "production_weight": 0.0,
                })
        raw_records.append(raw_node)
    return valid_at, raw_records, normalized, features


def integrate_transport(points, start, end):
    """Trapezoidal transport over available points with explicit gap quality."""
    pts = sorted((t, v) for t, v in points if start <= t <= end and v is not None)
    if len(pts) < 2 or pts[0][0] > start + timedelta(minutes=5) or pts[-1][0] < end - timedelta(minutes=5):
        return None
    total = 0.0
    max_gap = 0.0
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        dt = (t1 - t0).total_seconds()
        max_gap = max(max_gap, dt)
        total += 0.5 * (float(v0) + float(v1)) * dt
    return {"signed_transport_m": total, "max_sample_gap_hours": max_gap / 3600.0, "quality": "good" if max_gap <= 3600 * 1.1 else "coarse"}


def build_transport_features(normalized):
    groups = {}
    for row in normalized:
        if row["variable_or_evidence_type"] != "shoreward_current":
            continue
        key = (row["shoreline_cell"], row["requested_offshore_offset_km"], row["vertical_role"], row["cast"])
        groups.setdefault(key, []).append((datetime.fromisoformat(row["valid_at"]), float(row["value_or_status"])))
    out = []
    for (cell, offset, role, cast), points in groups.items():
        points.sort()
        if cast == "forecast":
            start = points[0][0]
            for hours in (1, 3, 6, 12):
                result = integrate_transport(points, start, start + timedelta(hours=hours))
                if result:
                    out.append({
                        "feature_id": f"ngofs2_{role}_shoreward_forward_transport_{hours}h_m", "feature_version": "ngofs2_regulargrid_v1",
                        "target_time": (start + timedelta(hours=hours)).isoformat(), "available_by_target_time": False,
                        "shoreline_cell": cell, "requested_offshore_offset_km": offset, "value": result["signed_transport_m"], "units": "m",
                        "max_sample_gap_hours": result["max_sample_gap_hours"], "quality": result["quality"],
                        "source_class": "MODEL_DERIVED", "production_weight": 0.0,
                    })
        else:
            end = points[-1][0]
            for hours in (1, 3, 6):
                result = integrate_transport(points, end - timedelta(hours=hours), end)
                if result:
                    out.append({
                        "feature_id": f"ngofs2_{role}_shoreward_antecedent_transport_{hours}h_m", "feature_version": "ngofs2_regulargrid_v1",
                        "target_time": end.isoformat(), "available_by_target_time": False,
                        "shoreline_cell": cell, "requested_offshore_offset_km": offset, "value": result["signed_transport_m"], "units": "m",
                        "max_sample_gap_hours": result["max_sample_gap_hours"], "quality": result["quality"],
                        "source_class": "MODEL_DERIVED", "production_weight": 0.0,
                    })
    return out


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--casts", default="nowcast,forecast", help="comma-separated nowcast,forecast")
    args = p.parse_args()
    casts = [x.strip() for x in args.casts.split(",") if x.strip()]
    if not set(casts) <= {"nowcast", "forecast"}:
        raise SystemExit("--casts must contain only nowcast,forecast")
    retrieved = datetime.now(timezone.utc)
    targets = load_targets()
    manifest = {
        "schema_version": "1.0", "retrieved_at": retrieved.isoformat(), "status": "failed", "source_class": "MODEL",
        "production_action": "NO_CHANGE", "target_config": "model_data/ngofs2_target_cells.json", "casts_requested": casts,
    }
    all_raw, all_norm, all_features = [], [], []
    cast_meta = []
    try:
        for cast in casts:
            ref, cycle, ref_url, failures = open_reference(cast, retrieved)
            try:
                nodes = select_nodes(ref, targets)
            finally:
                ref.close()
            leads = FORECAST_LEADS if cast == "forecast" else NOWCAST_LEADS
            opened, failed = [], []
            for lead in leads:
                url = regulargrid_url(cycle, cast, lead)
                try:
                    ds = Dataset(url, "r")
                    try:
                        valid_at, raw, norm, feats = extract_one_file(ds, url, cycle, cast, lead, nodes, retrieved)
                    finally:
                        ds.close()
                    all_raw.extend(raw); all_norm.extend(norm); all_features.extend(feats)
                    opened.append({"lead_hour": lead, "valid_at": valid_at.isoformat(), "source_url": url})
                except Exception as exc:
                    failed.append({"lead_hour": lead, "source_url": url, "error_type": type(exc).__name__, "error": str(exc)[:240]})
            if len(opened) < 2:
                raise RuntimeError(f"Insufficient {cast} regular-grid slices opened: {opened}; failures={failed}")
            cast_meta.append({
                "cast": cast, "model_initialized_at": cycle.isoformat(), "reference_url": ref_url, "failed_newer_cycle_attempts": failures,
                "selected_nodes": nodes, "opened_slices": opened, "failed_slices": failed,
            })
        all_features.extend(build_transport_features(all_norm))
        raw_payload = json.dumps({"casts": cast_meta, "records": all_raw}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw_payload).hexdigest()
        archive = HERE / "public_archive" / "ngofs2_shoreline_grid_subset" / f"{digest}.json.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(gzip.compress(raw_payload, mtime=0))
        for row in all_norm:
            row["source_hash"] = digest
            row["normalizer_version"] = "ngofs2_regulargrid_v1"
        for row in all_features:
            row["source_hash"] = digest
        norm_path = HERE / "ngofs2_shoreline_grid_normalized.csv"
        feat_path = HERE / "ngofs2_shoreline_grid_features.csv"
        write_csv(norm_path, all_norm)
        write_csv(feat_path, all_features)
        manifest.update({
            "status": "complete", "casts": cast_meta, "normalized_rows": len(all_norm), "derived_feature_rows": len(all_features),
            "raw_subset_sha256": digest, "raw_subset_archive": str(archive.relative_to(HERE)),
            "normalized_data": str(norm_path.relative_to(HERE)), "derived_features": str(feat_path.relative_to(HERE)),
            "guardrails": [
                "MODEL guidance only; never describe as observed current, salinity or temperature.",
                "Public shoreline anchors only; no private-home coordinates are used or published.",
                "Multiple wet nodes along each offshore transect replace silent distant named-station substitution.",
                "Shoreward bearings are provisional and require +/-15 degree sensitivity before model promotion.",
                "available_at is conservatively retrieval time; historical backtests require archived-cycle availability semantics.",
                "No production weight until held-out incremental value and calibration are demonstrated."
            ],
        })
    except Exception as exc:
        manifest.update({"error_type": type(exc).__name__, "error": str(exc)})
    out = HERE / "ngofs2_shoreline_grid_manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

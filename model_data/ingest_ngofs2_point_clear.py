#!/usr/bin/env python3
"""Extract Point Clear NGOFS2 station guidance without downloading full model fields.

The output is MODEL guidance, never a direct observation.  It is intended to
measure the transport/alignment state independently of the local hypoxia state.
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
TARGET_NAME = "Point Clear"
# Eastern Shore at Point Clear is west-facing; +east is the provisional shoreward normal.
SHOREWARD_BEARING_DEG_TRUE = 90.0


def cycle_candidates(now: datetime, count: int = 8):
    """Newest plausible posted cycle first; keep retry history bounded."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    # NOAA posts NGOFS2 roughly 70 minutes after the cycle start.  A 90-minute
    # cushion avoids repeatedly requesting a cycle that is still being posted.
    cutoff = now.astimezone(timezone.utc) - timedelta(minutes=90)
    out = []
    day = cutoff.date()
    for back in range(3):
        d = day - timedelta(days=back)
        for hour in reversed(CYCLE_HOURS):
            candidate = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
            if candidate <= cutoff:
                out.append(candidate)
                if len(out) >= count:
                    return out
    return out


def station_url(cycle: datetime, cast: str):
    if cast not in {"nowcast", "forecast"}:
        raise ValueError("cast must be nowcast or forecast")
    date = cycle.strftime("%Y%m%d")
    return (
        f"{BASE}/{cycle:%Y/%m/%d}/"
        f"ngofs2.t{cycle:%H}z.{date}.stations.{cast}.nc"
    )


def _decode_station_names(variable):
    raw = variable[:]
    if getattr(raw, "dtype", None) is not None and raw.dtype.kind in {"U", "O"}:
        return [str(x).strip() for x in raw.tolist()]
    if getattr(raw, "dtype", None) is not None and raw.dtype.kind == "S":
        if raw.ndim == 1:
            return [bytes(x).decode("utf-8", errors="replace").strip() for x in raw]
        return [str(x).strip() for x in chartostring(raw).tolist()]
    return [str(x).strip() for x in raw.tolist()]


def find_station_index(names, target=TARGET_NAME):
    normalized = [str(x).strip().casefold().replace("+", " ") for x in names]
    want = target.casefold()
    exact = [i for i, name in enumerate(normalized) if name == want]
    if len(exact) == 1:
        return exact[0]
    contains = [i for i, name in enumerate(normalized) if want in name]
    if len(contains) == 1:
        return contains[0]
    raise ValueError(f"Could not uniquely resolve station {target!r}; matches={contains}")


def choose_vertical_indices(sigmas):
    vals = [float(x) for x in sigmas]
    if not vals:
        raise ValueError("No sigma layers")
    # FVCOM sigma layers are 0 near the surface and -1 near the bed.
    surface = max(range(len(vals)), key=lambda i: vals[i])
    bottom = min(range(len(vals)), key=lambda i: vals[i])
    return surface, bottom


def shoreward_component(u_east, v_north, bearing_deg_true=SHOREWARD_BEARING_DEG_TRUE):
    """Project east/north velocity onto a true-bearing shoreward unit vector."""
    rad = math.radians(float(bearing_deg_true))
    return float(u_east) * math.sin(rad) + float(v_north) * math.cos(rad)


def integrate_trapezoid(points):
    """Return signed displacement in meters for (aware_datetime, m/s) points."""
    pts = sorted(points)
    total = 0.0
    for (ta, va), (tb, vb) in zip(pts, pts[1:]):
        dt = (tb - ta).total_seconds()
        if 0 < dt <= 1800:  # station output is 6-min; reject large gaps
            total += (float(va) + float(vb)) * 0.5 * dt
    return total


def summarize_transport(rows, reference_time):
    bottom = [r for r in rows if r["vertical_role"] == "bottom" and r["parameter"] == "shoreward_current"]
    points = [(datetime.fromisoformat(r["valid_at"]), float(r["value"])) for r in bottom]
    out = {}
    for hours in (1, 3, 6):
        start = reference_time - timedelta(hours=hours)
        selected = [(t, v) for t, v in points if start <= t <= reference_time]
        if len(selected) < 2:
            out[str(hours)] = {"count": len(selected), "mean_m_s": None, "signed_transport_m": None}
            continue
        out[str(hours)] = {
            "count": len(selected),
            "mean_m_s": sum(v for _, v in selected) / len(selected),
            "signed_transport_m": integrate_trapezoid(selected),
        }
    return out


def _as_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def extract_from_dataset(ds, source_url, retrieved_at, cycle):
    required = {"name_station", "lon", "lat", "h", "siglay", "time", "u", "v", "temp", "salinity", "zeta"}
    missing = sorted(required - set(ds.variables))
    if missing:
        raise ValueError(f"NGOFS2 station dataset missing variables: {missing}")

    names = _decode_station_names(ds.variables["name_station"])
    idx = find_station_index(names)
    lon = _as_float(ds.variables["lon"][idx])
    lat = _as_float(ds.variables["lat"][idx])
    depth = _as_float(ds.variables["h"][idx])
    sigmas = ds.variables["siglay"][:, idx]
    surface_i, bottom_i = choose_vertical_indices(sigmas)

    tvar = ds.variables["time"]
    times = num2date(tvar[:], units=tvar.units, calendar=getattr(tvar, "calendar", "standard"), only_use_cftime_datetimes=False)
    rows = []
    for ti, valid in enumerate(times):
        if valid.tzinfo is None:
            valid = valid.replace(tzinfo=timezone.utc)
        else:
            valid = valid.astimezone(timezone.utc)
        zeta = _as_float(ds.variables["zeta"][ti, idx])
        for vertical_role, layer_i in (("surface", surface_i), ("bottom", bottom_i)):
            u = _as_float(ds.variables["u"][ti, layer_i, idx])
            v = _as_float(ds.variables["v"][ti, layer_i, idx])
            temp = _as_float(ds.variables["temp"][ti, layer_i, idx])
            sal = _as_float(ds.variables["salinity"][ti, layer_i, idx])
            values = {
                "eastward_current": (u, "m/s"),
                "northward_current": (v, "m/s"),
                "shoreward_current": (shoreward_component(u, v) if u is not None and v is not None else None, "m/s"),
                "water_temperature": (temp, "degC"),
                "salinity": (sal, "1e-3"),
            }
            for parameter, (value, unit) in values.items():
                if value is None:
                    continue
                rows.append({
                    "source_id": "noaa_ngofs2_point_clear_station",
                    "evidence_class": "MODEL",
                    "station_name": names[idx],
                    "station_index": idx,
                    "lat": lat,
                    "lon": lon,
                    "bathymetry_m": depth,
                    "vertical_role": vertical_role,
                    "sigma_layer_index": layer_i,
                    "sigma_value": _as_float(sigmas[layer_i]),
                    "parameter": parameter,
                    "value": value,
                    "unit": unit,
                    "valid_at": valid.isoformat(),
                    "model_initialized_at": cycle.isoformat(),
                    "available_at": retrieved_at.isoformat(),
                    "ingested_at": retrieved_at.isoformat(),
                    "source_url": source_url,
                    "shoreline_cell": "Point Clear/Grand Hotel",
                    "production_weight": 0.0,
                })
        if zeta is not None:
            rows.append({
                "source_id": "noaa_ngofs2_point_clear_station",
                "evidence_class": "MODEL",
                "station_name": names[idx], "station_index": idx, "lat": lat, "lon": lon,
                "bathymetry_m": depth, "vertical_role": "surface", "sigma_layer_index": None,
                "sigma_value": None, "parameter": "water_surface_elevation", "value": zeta, "unit": "m",
                "valid_at": valid.isoformat(), "model_initialized_at": cycle.isoformat(),
                "available_at": retrieved_at.isoformat(), "ingested_at": retrieved_at.isoformat(),
                "source_url": source_url, "shoreline_cell": "Point Clear/Grand Hotel", "production_weight": 0.0,
            })
    metadata = {
        "station_name": names[idx], "station_index": idx, "lat": lat, "lon": lon,
        "bathymetry_m": depth, "surface_sigma_index": surface_i, "bottom_sigma_index": bottom_i,
        "surface_sigma": _as_float(sigmas[surface_i]), "bottom_sigma": _as_float(sigmas[bottom_i]),
    }
    return rows, metadata


def open_latest(cast, now):
    errors = []
    for cycle in cycle_candidates(now):
        url = station_url(cycle, cast)
        try:
            ds = Dataset(url, mode="r")
            return ds, url, cycle, errors
        except Exception as exc:
            errors.append({"url": url, "error_type": type(exc).__name__})
    raise RuntimeError(f"Unable to open any recent NGOFS2 station dataset: {errors}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cast", choices=["nowcast", "forecast"], default="nowcast")
    args = parser.parse_args()
    retrieved = datetime.now(timezone.utc)
    manifest = {
        "schema_version": "1.0", "retrieved_at": retrieved.isoformat(), "cast": args.cast,
        "status": "failed", "evidence_class": "MODEL", "production_action": "NO_CHANGE",
    }
    try:
        ds, url, cycle, failed_attempts = open_latest(args.cast, retrieved)
        try:
            rows, metadata = extract_from_dataset(ds, url, retrieved, cycle)
        finally:
            ds.close()
        if not rows:
            raise ValueError("NGOFS2 extraction returned no rows")
        payload = json.dumps({"source_url": url, "cycle": cycle.isoformat(), "metadata": metadata, "rows": rows}, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(payload).hexdigest()
        archive = HERE / "public_archive" / "ngofs2_subset" / f"{digest}.json.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(gzip.compress(payload, mtime=0))

        dest = HERE / "ngofs2_point_clear_normalized.csv"
        with dest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        valid_times = [datetime.fromisoformat(r["valid_at"]) for r in rows if r["parameter"] == "shoreward_current" and r["vertical_role"] == "bottom"]
        reference = max(t for t in valid_times if t <= retrieved) if any(t <= retrieved for t in valid_times) else max(valid_times)
        manifest.update({
            "status": "complete", "source_url": url, "model_initialized_at": cycle.isoformat(),
            "failed_newer_attempts": failed_attempts, "normalized_rows": len(rows),
            "subset_sha256": digest, "subset_archive": str(archive.relative_to(HERE)),
            "station": metadata, "reference_valid_at": reference.isoformat(),
            "transport_windows": summarize_transport(rows, reference),
        })
    except Exception as exc:
        manifest.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]})
    manifest["guardrails"] = [
        "NGOFS2 is MODEL guidance and is not a direct current, salinity, temperature, water-level or oxygen observation.",
        "Point Clear shoreward projection currently uses a west-facing shoreline geometry: true bearing 090 degrees is shoreward (+east).",
        "The station extraction is a first transport implementation; other shoreline cells still require their own station/grid geometry and validation.",
        "No production weight changes until event/control held-out incremental value is demonstrated.",
        "The content-addressed archive stores only the authoritative subset used by this pipeline, not the full NOAA model file.",
    ]
    (HERE / "ngofs2_point_clear_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if manifest["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

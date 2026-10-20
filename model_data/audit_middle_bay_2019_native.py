"""Read-only native ASCII audit for NOAA NCEI 0224293 (Middle Bay, 2019).

Requires an explicitly supplied original .txt; does not download, normalize UTC,
select bottom cells, publish forecasts, or promote production features.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

SOURCE_URL = ("https://www.ncei.noaa.gov/data/oceans/archive/arc0171/"
              "0224293/1.1/data/0-data/middlebay_hyd_2019.txt")
ORIGINAL_SHA256 = "49e04d4903d6f6edc4f6bbbc91e9b7e81a6c6ed560318a0621d1d9c454c5e7fb"
REQUIRED_FIELDS = ("yeardata", "jday", "timedata", "stationid",
                   "Dissoved Oxygen mgl", "Dissoved Oxygen mgl flag",
                   "Dissoved Oxygen percent", "Dissoved Oxygen Percent flag",
                   "Water Temperature", "Water Temperature Flag",
                   "Salinity", "Salinity Flag", "Pressure", "Water Height",
                   "Water Height Flag")
NATIVE_PARAMETERS = {
    "do_mg_l": "Dissoved Oxygen mgl",
    "do_percent": "Dissoved Oxygen percent",
    "salinity": "Salinity",
    "temperature_native_c": "Water Temperature",
    "pressure_native_psi_g": "Pressure",
    "water_height_native_unresolved_units": "Water Height",
}


def audit_bytes(data, require_original=True):
    digest = hashlib.sha256(data).hexdigest()
    if require_original and digest != ORIGINAL_SHA256:
        raise ValueError("source SHA-256 mismatch; cannot silently substitute revised archive")
    decoded = data.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(decoded))
    if not set(REQUIRED_FIELDS).issubset(reader.fieldnames or []):
        raise ValueError("native header mismatch")
    rows = list(reader)
    if not rows:
        raise ValueError("no records")
    if any(None in row or row.get(None) is not None for row in rows):
        raise ValueError("native row column-width mismatch")
    stations = Counter()
    years = Counter()
    months = Counter()
    day_key_count = Counter()
    quality = {k: Counter() for k in REQUIRED_FIELDS if "flag" in k.lower()}
    measures = {k: [] for k in NATIVE_PARAMETERS}
    for row in rows:
        try:
            year = int(row["yeardata"])
            doy = int(row["jday"])
            native_time = int(row["timedata"])
            if year != 2019 or not 1 <= doy <= 365 or not 0 <= native_time <= 2400:
                raise ValueError("unexpected native calendar field")
            # Date only; source's wall-clock timezone and 2400 convention remain unresolved.
            day = datetime(year, 1, 1) + timedelta(days=doy - 1)
            stations[row["stationid"]] += 1
            years[year] += 1
            months[day.strftime("%Y-%m")] += 1
            day_key_count[(year, doy, native_time, row["stationid"])] += 1
            for field in quality:
                quality[field][row[field].strip()] += 1
            for name, field in NATIVE_PARAMETERS.items():
                value = float(row[field])
                if not math.isfinite(value):
                    raise ValueError("non-finite native value")
                measures[name].append(value)
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError("unparseable native record") from error
    summary = {}
    for name, values in measures.items():
        summary[name] = {"count": len(values), "min": min(values), "max": max(values)}
    summary["do_mg_l"]["below_2"] = sum(x < 2 for x in measures["do_mg_l"])
    return {
        "schema": "jubilee_j09_ncei_0224293_native_audit/v1",
        "source_url": SOURCE_URL,
        "raw_sha256": digest,
        "raw_bytes": len(data),
        "rows": len(rows),
        "native_station_id_counts": dict(stations),
        "year_counts": {str(k): v for k, v in sorted(years.items())},
        "nominal_month_counts": dict(sorted(months.items())),
        "distinct_native_day_time_station_keys": len(day_key_count),
        "duplicate_native_keys": sum(v - 1 for v in day_key_count.values() if v > 1),
        "native_quality_flags": {k: dict(v) for k, v in quality.items()},
        "measure_ranges": summary,
        "clock_timezone": "UNKNOWN_NOT_NORMALIZED",
        "sensor_depth_geometry": "UNKNOWN_NOT_BOTTOM_VERIFIED",
        "water_height_units": "UNRESOLVED_NOT_USED",
        "pressure_units": "psi gauge per NCEI archived provider correspondence, not converted",
        "point_clear_current_rows": 0,
        "forecast_production_weight": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_bytes(args.raw_path.read_bytes()), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Exploratory backtest for antecedent public water-quality features.

This script is deliberately conservative. It does not change production weights.
It compares observations in the 1/3/7/14 days preceding confirmed Jubilee dates
with same-station/same-parameter observations from the same calendar month that
are at least 7 days away from any confirmed event. Promotion is forbidden until
there are enough independent confirmed events and observations.
"""
from __future__ import annotations

import csv
import json
import math
import pathlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "water_quality_normalized.csv"
EVENTS = HERE / "event_history.json"
OUT = HERE / "water_quality_backtest.json"

LAGS = (1, 3, 7, 14)
MIN_DISTINCT_EVENTS_FOR_PROMOTION = 10
MIN_EVENT_LINKED_OBSERVATIONS_FOR_PROMOTION = 50


def as_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_date(x):
    try:
        return datetime.strptime(x, "%Y-%m-%d").date()
    except Exception:
        return None


def log10_safe(v):
    return math.log10(v) if v is not None and v > 0 else None


def load_events():
    obj = json.loads(EVENTS.read_text(encoding="utf-8"))
    out = []
    for e in obj.get("events", []):
        if e.get("classification") == "confirmed_jubilee":
            d = parse_date(e.get("event_date_ct", ""))
            if d:
                out.append((e["event_id"], d, e.get("scale"), e.get("location", {}).get("label")))
    return out


def is_enterococcus(parameter):
    p = (parameter or "").lower()
    return "enterococcus" in p or "enterococci" in p


def transform(parameter, value):
    if is_enterococcus(parameter):
        return log10_safe(value), "log10_raw_value"
    return value, "raw_value"


def main():
    events = load_events()
    event_dates = [d for _, d, _, _ in events]
    rows = []
    if DATA.exists():
        with DATA.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                d = parse_date(r.get("sample_date", ""))
                v = as_float(r.get("value"))
                if not d or v is None:
                    continue
                tv, transform_name = transform(r.get("parameter"), v)
                if tv is None:
                    continue
                rows.append({**r, "date": d, "numeric": v, "transformed": tv, "transform": transform_name})

    results = []
    total_event_linked = 0
    event_ids_with_data = set()

    groups = defaultdict(list)
    for r in rows:
        key = (r.get("source_id"), r.get("station_id"), r.get("parameter"), r.get("unit"), r.get("transform"))
        groups[key].append(r)

    for lag in LAGS:
        for key, grows in groups.items():
            event_values = []
            control_values = []
            linked_events = set()

            for event_id, edate, _, _ in events:
                lo = edate - timedelta(days=lag)
                for r in grows:
                    if lo <= r["date"] <= edate:
                        event_values.append(r["transformed"])
                        linked_events.add(event_id)

            for r in grows:
                # matched by month-of-year, excluding observations close to any event
                if not any(r["date"].month == ed.month for ed in event_dates):
                    continue
                distance = min((abs((r["date"] - ed).days) for ed in event_dates), default=9999)
                if distance >= 7:
                    control_values.append(r["transformed"])

            if not event_values or not control_values:
                continue

            total_event_linked += len(event_values)
            event_ids_with_data.update(linked_events)
            ev_med = median(event_values)
            ctl_med = median(control_values)
            results.append({
                "lag_days": lag,
                "source_id": key[0],
                "station_id": key[1],
                "parameter": key[2],
                "unit": key[3],
                "transform": key[4],
                "event_observation_count": len(event_values),
                "control_observation_count": len(control_values),
                "distinct_linked_events": len(linked_events),
                "event_median": ev_med,
                "control_median": ctl_med,
                "median_difference": ev_med - ctl_med,
                "direction": "higher_before_events" if ev_med > ctl_med else ("lower_before_events" if ev_med < ctl_med else "no_difference"),
            })

    sufficient = (
        len(event_ids_with_data) >= MIN_DISTINCT_EVENTS_FOR_PROMOTION
        and total_event_linked >= MIN_EVENT_LINKED_OBSERVATIONS_FOR_PROMOTION
    )

    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "method": "Exploratory same-station/same-parameter antecedent-window comparison with same-month controls >=7 days from confirmed events.",
        "confirmed_events_in_database": len(events),
        "confirmed_events_with_any_water_quality_data": len(event_ids_with_data),
        "event_linked_observations_across_tests": total_event_linked,
        "promotion_threshold": {
            "minimum_distinct_events": MIN_DISTINCT_EVENTS_FOR_PROMOTION,
            "minimum_event_linked_observations": MIN_EVENT_LINKED_OBSERVATIONS_FOR_PROMOTION,
        },
        "sufficient_for_production_promotion": sufficient,
        "production_action": "NO_CHANGE" if not sufficient else "REQUIRES_FORMAL_OUT_OF_SAMPLE_VALIDATION",
        "guardrail": "No public antecedent water-quality variable receives positive production weight from this exploratory backtest alone.",
        "results": sorted(results, key=lambda x: (x["lag_days"], x["source_id"], x["station_id"], x["parameter"] or "")),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "results"}, indent=2))


if __name__ == "__main__":
    main()

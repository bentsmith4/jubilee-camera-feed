#!/usr/bin/env python3
"""Measure individual-event recovery against aggregate historical benchmarks.

The ratio is a recovery-progress diagnostic, not an estimate of true Jubilee
frequency or reporting completeness. Aggregate newspaper counts can include
spatially broad/duplicated reporting and lack event-level dates/locations.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = HERE / "event_history.json"
CANDIDATES = HERE / "historical_event_candidate_additions_20260906.json"
OUT = HERE / "historical_recovery_status.json"


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    events_doc = json.loads(EVENTS.read_text(encoding="utf-8"))
    candidate_doc = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    benchmarks = candidate_doc.get("aggregate_historical_benchmarks", [])
    if not benchmarks:
        raise SystemExit("No aggregate historical benchmark available")
    benchmark = next((x for x in benchmarks if x.get("benchmark_id") == "mobile_press_register_1946_1971_aggregate"), benchmarks[0])
    start_s, end_s = benchmark["period"].split("-")
    start, end = date(int(start_s), 1, 1), date(int(end_s), 12, 31)
    recovered = []
    for event in events_doc.get("events", []):
        d = event.get("event_date_ct")
        if not d:
            continue
        parsed = _date(d)
        if start <= parsed <= end:
            recovered.append({
                "event_id": event.get("event_id"),
                "event_date_ct": d,
                "location": (event.get("location") or {}).get("label"),
                "confidence": event.get("confidence"),
            })
    aggregate = int(benchmark["reported_jubilees"])
    output = {
        "schema_version": "1.0",
        "benchmark_id": benchmark["benchmark_id"],
        "period": benchmark["period"],
        "aggregate_reported_jubilees": aggregate,
        "canonical_individually_dated_events_in_period": len(recovered),
        "canonical_events": recovered,
        "individual_record_recovery_fraction_vs_aggregate": round(len(recovered) / aggregate, 6) if aggregate else None,
        "status": "LARGE_HISTORICAL_RECOVERY_GAP",
        "interpretation": "This fraction measures event-row recovery progress against an aggregate newspaper count. It is not event incidence, recall, sensitivity, or forecast skill.",
        "priority": "Recover individual 1946-1971 dates, shoreline locations and contemporaneous evidence, with Loesch 1946-1956 primary material first.",
        "guardrails": [
            "Do not manufacture event rows from aggregate counts.",
            "Do not assume uniform newspaper observation effort over time or shoreline.",
            "Deduplicate multiple stories describing the same Jubilee before admission.",
            "Preserve date/location uncertainty and source independence."
        ],
        "production_action": "NO_CHANGE"
    }
    OUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

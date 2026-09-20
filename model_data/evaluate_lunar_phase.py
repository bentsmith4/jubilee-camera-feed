#!/usr/bin/env python3
"""Leakage-safe descriptive test of lunar phase for Jubilee event dates.

This intentionally does not treat unreported days as non-events.  It evaluates
event-only phase clustering, preserves adjacent event days as shared episodes,
and keeps owner/scientific control candidates in a separate sensitivity layer.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


SYNODIC_MONTH_DAYS = 29.53058867
REFERENCE_NEW_MOON_UTC = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
REPRESENTATIVE_PREDAWN_HOUR_UTC = 11  # about 06:00 CDT; sub-day uncertainty is immaterial here

EPISODE_OVERRIDES = {
    "1971-08-07-point-clear-corridor": "1971-08-07-08-point-clear-episode",
    "1971-08-08-point-clear-corridor-major": "1971-08-07-08-point-clear-episode",
    "2026-08-29-fairhope-point-clear-multipocket": "2026-08-29-30-eastern-shore-episode",
    "2026-08-30-fairhope-north-of-pier-localized": "2026-08-29-30-eastern-shore-episode",
}


def phase_fraction(date_text: str) -> float:
    day = datetime.strptime(date_text, "%Y-%m-%d").replace(
        hour=REPRESENTATIVE_PREDAWN_HOUR_UTC, tzinfo=timezone.utc
    )
    elapsed_days = (day - REFERENCE_NEW_MOON_UTC).total_seconds() / 86400.0
    return (elapsed_days / SYNODIC_MONTH_DAYS) % 1.0


def phase_summary(date_text: str) -> dict:
    fraction = phase_fraction(date_text)
    age_days = fraction * SYNODIC_MONTH_DAYS
    illumination = (1.0 - math.cos(2.0 * math.pi * fraction)) / 2.0
    nearest_syzygy_days = min(
        age_days,
        SYNODIC_MONTH_DAYS - age_days,
        abs(age_days - SYNODIC_MONTH_DAYS / 2.0),
    )
    return {
        "date_ct": date_text,
        "phase_fraction_since_new": round(fraction, 6),
        "lunar_age_days": round(age_days, 3),
        "illumination_fraction": round(illumination, 4),
        "nearest_new_or_full_days": round(nearest_syzygy_days, 3),
    }


def circular_mean(fractions: list[float]) -> float:
    c = sum(math.cos(2.0 * math.pi * x) for x in fractions)
    s = sum(math.sin(2.0 * math.pi * x) for x in fractions)
    angle = math.atan2(s, c)
    return (angle / (2.0 * math.pi)) % 1.0


def rayleigh(fractions: list[float]) -> dict:
    n = len(fractions)
    c = sum(math.cos(2.0 * math.pi * x) for x in fractions)
    s = sum(math.sin(2.0 * math.pi * x) for x in fractions)
    resultant = math.hypot(c, s)
    r_bar = resultant / n
    z = n * r_bar * r_bar
    correction_1 = (2.0 * z - z * z) / (4.0 * n)
    correction_2 = (
        24.0 * z - 132.0 * z**2 + 76.0 * z**3 - 9.0 * z**4
    ) / (288.0 * n * n)
    p_approx = math.exp(-z) * (1.0 + correction_1 - correction_2)
    return {
        "n": n,
        "mean_resultant_length": round(r_bar, 6),
        "rayleigh_z": round(z, 6),
        "rayleigh_p_approx": round(max(0.0, min(1.0, p_approx)), 6),
        "circular_mean_phase_fraction": round(circular_mean(fractions), 6),
    }


def load_events(path: Path, ambiguous_1959_date: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for event in payload["events"]:
        if event.get("classification") != "confirmed_jubilee":
            continue
        event_date = event["event_date_ct"]
        if event["event_id"] == "1959-07-point-clear-south-grand-hotel":
            event_date = ambiguous_1959_date
        summary = phase_summary(event_date)
        rows.append(
            {
                "event_id": event["event_id"],
                "episode_id": EPISODE_OVERRIDES.get(event["event_id"], event["event_id"]),
                "date_precision": event.get("date_precision", "not_recorded"),
                **summary,
            }
        )
    return rows


def collapse_episodes(events: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for event in events:
        grouped.setdefault(event["episode_id"], []).append(event)
    episodes = []
    for episode_id, members in sorted(grouped.items()):
        phases = [m["phase_fraction_since_new"] for m in members]
        mean_phase = circular_mean(phases)
        episodes.append(
            {
                "episode_id": episode_id,
                "member_event_ids": [m["event_id"] for m in members],
                "member_dates_ct": [m["date_ct"] for m in members],
                "phase_fraction_since_new": round(mean_phase, 6),
                "nearest_new_or_full_days": round(
                    min(
                        mean_phase * SYNODIC_MONTH_DAYS,
                        SYNODIC_MONTH_DAYS - mean_phase * SYNODIC_MONTH_DAYS,
                        abs(mean_phase * SYNODIC_MONTH_DAYS - SYNODIC_MONTH_DAYS / 2.0),
                    ),
                    3,
                ),
            }
        )
    return episodes


def evaluate(
    event_history: Path,
    source_blob_sha: str | None = None,
    source_path_label: str | None = None,
) -> dict:
    primary_events = load_events(event_history, "1959-07-07")
    alternate_events = load_events(event_history, "1959-07-08")
    primary_episodes = collapse_episodes(primary_events)
    alternate_episodes = collapse_episodes(alternate_events)
    episode_phases = [x["phase_fraction_since_new"] for x in primary_episodes]
    loo_r = []
    for i in range(len(episode_phases)):
        loo_r.append(rayleigh(episode_phases[:i] + episode_phases[i + 1 :])["mean_resultant_length"])
    near_syzygy = sum(x["nearest_new_or_full_days"] <= 3.0 for x in primary_episodes)
    return {
        "schema_version": "1.0",
        "scope": "RESEARCH_ONLY_LUNAR_PHASE_FEATURE_AUDIT",
        "production_action": "NO_CHANGE",
        "source_provenance": {
            "event_history_path": source_path_label or str(event_history),
            "event_history_git_blob_sha": source_blob_sha,
            "input_projection": "confirmed_jubilee rows and their date/date-precision fields",
        },
        "method": {
            "phase_algorithm": "mean synodic month from 2000-01-06T18:14Z reference new moon",
            "representative_time": "11:00 UTC on event date (approximately 06:00 CDT)",
            "validation": "event-only circular clustering; adjacent dates from one physical episode collapsed; no-report days never used as negatives",
            "test": "small-sample corrected Rayleigh approximation",
        },
        "sample": {
            "confirmed_event_rows": len(primary_events),
            "independent_event_episodes": len(primary_episodes),
            "clean_matched_non_event_controls": 0,
        },
        "event_level": rayleigh([x["phase_fraction_since_new"] for x in primary_events]),
        "episode_level_primary_1959_date": rayleigh(episode_phases),
        "episode_level_alternate_1959_date": rayleigh(
            [x["phase_fraction_since_new"] for x in alternate_episodes]
        ),
        "leave_one_episode_out_mean_resultant_length": {
            "min": round(min(loo_r), 6),
            "max": round(max(loo_r), 6),
        },
        "episodes_within_3_days_of_new_or_full": {
            "count": near_syzygy,
            "n": len(primary_episodes),
            "fraction": round(near_syzygy / len(primary_episodes), 6),
            "uniform_calendar_expectation": round(12.0 / SYNODIC_MONTH_DAYS, 6),
        },
        "same_day_spatial_falsification": {
            "date_ct": "2024-06-12",
            "finding": "Point Clear confirmed Jubilee and May Day scoped reported-nothing candidate necessarily have identical lunar phase; lunar phase cannot explain within-morning shoreline location/contact contrast.",
            **phase_summary("2024-06-12"),
        },
        "owner_reported_negative_sensitivity_only": [
            {"classification": "owner_first_person_scoped_non_event_not_clean_control", **phase_summary("2026-09-07")},
            {"classification": "owner_reported_eastern_shore_non_event_not_clean_control", **phase_summary("2026-09-12")},
        ],
        "scientific_near_miss_sensitivity_only": {
            "classification": "scientific_near_miss_not_clean_control",
            "description": "1971-08-16 severe offshore hypoxia approached Point Clear without documented shoreline Jubilee",
            **phase_summary("1971-08-16"),
        },
        "decision": {
            "status": "BLOCKED_BY_DATA",
            "production_weight": 0.0,
            "incremental_value": "NOT_ESTABLISHED",
            "reason": "No statistically persuasive event-phase clustering and zero verified matched non-event controls; lunar phase also cannot discriminate the strongest same-day Point Clear-versus-May Day spatial contrast.",
            "promotion_requirement": "Test only after enough independently observed event/control mornings exist for episode-blocked incremental scoring against seasonal/tidal baselines.",
        },
        "events": primary_events,
        "episodes": primary_episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-history", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-blob-sha")
    parser.add_argument("--source-path-label")
    args = parser.parse_args()
    result = evaluate(args.event_history, args.source_blob_sha, args.source_path_label)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()

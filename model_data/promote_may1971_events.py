#!/usr/bin/env python3
"""Idempotent promotion of reviewed historical Jubilee events.

This updates the existing canonical event_history.json; it does not create a
parallel event database. Only explicitly reviewed evidence rows are admitted.
Scientific near misses and observation-effort-only records stay in their
separate canonical layers.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = HERE / "event_history.json"

ADDITIONS = [
    {
        "event_id": "1971-08-07-point-clear-corridor",
        "event_date_ct": "1971-08-07",
        "date_precision": "exact_primary_scientific_report",
        "classification": "confirmed_jubilee",
        "scale": "unspecified",
        "location": {
            "label": "Eastern Shore north and/or south of Great Point Clear",
            "precision": "primary_scientific_paper_corridor",
            "continuous_boundary_claimed": False,
        },
        "confidence": 0.99,
        "evidence": [{
            "type": "primary_scientific_observation_report",
            "independence_group": "may_1971_aug07_primary",
            "supports": ["occurrence", "exact_date", "early_morning_timing", "Eastern Shore Great Point Clear corridor", "preceded_by_extensive_bottom_hypoxia"],
        }],
        "provenance": "Edwin B. May, 1973, Extensive Oxygen Depletion in Mobile Bay, Alabama, Limnology and Oceanography 18(3), reports early-morning Jubilees on Aug. 7 and Aug. 8, 1971 after extensive Aug. 5-6 bottom oxygen depletion.",
        "source_urls": ["https://doi.org/10.4319/lo.1973.18.3.0353"],
        "notes": "Exact shoreline segment active on Aug. 7 remains spatially ambiguous within the north/south Great Point Clear corridor; do not infer continuous shoreline coverage.",
    },
    {
        "event_id": "1971-08-08-point-clear-corridor-major",
        "event_date_ct": "1971-08-08",
        "date_precision": "exact_primary_scientific_report",
        "classification": "confirmed_jubilee",
        "scale": "extensive",
        "location": {
            "label": "Eastern Shore north and south of Great Point Clear; severe effects south of Great Point Clear",
            "precision": "primary_scientific_paper",
            "continuous_boundary_claimed": False,
        },
        "confidence": 0.995,
        "evidence": [{
            "type": "primary_scientific_observation_report",
            "independence_group": "may_1971_aug08_primary",
            "supports": ["occurrence", "exact_date", "early_morning_timing", "extensive_scale", "north_and_south_of_Great_Point_Clear", "post_event_major_fish_kill", "flounder", "worm_eels", "crustaceans"],
        }],
        "provenance": "Edwin B. May, 1973, describes an extensive Aug. 8, 1971 Jubilee along the Eastern Shore north and south of Great Point Clear after extensive bottom oxygen depletion.",
        "source_urls": ["https://doi.org/10.4319/lo.1973.18.3.0353"],
        "notes": "May reports especially severe mortality along roughly 6 km of shoreline south of Great Point Clear. Preserve event extent as reported rather than converting it to a continuous modern shoreline-cell label.",
    },
    {
        "event_id": "1971-08-26-north-of-daphne",
        "event_date_ct": "1971-08-26",
        "date_precision": "exact_primary_scientific_measurement",
        "classification": "confirmed_jubilee",
        "scale": "localized_measured_event",
        "location": {
            "label": "north of Daphne",
            "precision": "primary_scientific_paper",
            "continuous_boundary_claimed": False,
        },
        "confidence": 0.995,
        "evidence": [{
            "type": "primary_scientific_measurement_during_jubilee",
            "independence_group": "may_1971_aug26_primary",
            "supports": ["occurrence", "exact_date", "four_hour_duration", "north_of_Daphne", "bottom_DO_0_to_1_6_mg_L_mean_0_7", "surface_DO_mean_2_6_mg_L", "water_depth_1_5_m"],
        }],
        "provenance": "Edwin B. May, 1973, reports a four-hour Jubilee north of Daphne on Aug. 26, 1971 and provides dissolved-oxygen measurements during the event in approximately 1.5 m water.",
        "source_urls": ["https://doi.org/10.4319/lo.1973.18.3.0353"],
        "notes": "Exceptionally valuable positive because oxygen was measured during the Jubilee: bottom DO 0-1.6 mg/L, mean about 0.7 mg/L; surface mean about 2.6 mg/L.",
    },
    {
        "event_id": "2017-08-26-fairhope-yacht-club",
        "event_date_ct": "2017-08-26",
        "date_precision": "day_resolved_by_independent_first_person_accounts_and_calendar_context",
        "classification": "confirmed_jubilee",
        "scale": "mini_localized",
        "location": {
            "label": "Fairhope shoreline toward Fairhope Yacht Club",
            "precision": "first_person_paddle_route_and_shoreline_activity",
            "continuous_boundary_claimed": False,
        },
        "confidence": 0.975,
        "evidence": [
            {
                "type": "first_person_local_paddle_report",
                "independence_group": "2017_08_26_dining_with_mimi_fairhope",
                "supports": ["occurrence", "Saturday_morning", "Fairhope_shoreline", "toward_Yacht_Club", "flounder", "crabs", "shrimp", "stingray", "catfish", "dense_birds", "people_with_nets_buckets_and_ice_chests"],
            },
            {
                "type": "independent_first_person_local_blog_report",
                "independence_group": "2017_08_mobile_bay_runner_mini_jubilee",
                "supports": ["same_weekend_occurrence", "tons_of_crabs", "shrimp", "flounder", "eels", "many_people_along_the_bay"],
            },
        ],
        "provenance": "Dining With Mimi describes a Jubilee already underway on the author's regular Saturday Fairhope paddle, with the group paddling toward the Yacht Club and observing shoreline harvest activity, dense birds, and multiple Jubilee species. The author says the week began with the eclipse and ended with the Jubilee. Mobile Bay Runner independently posted on Sunday Aug. 27, 2017 that a mini-Jubilee occurred 'this weekend' and described crabs, shrimp, flounder, eels and many people along the Bay. The 2017 eclipse was Monday Aug. 21; together the accounts resolve the event to Saturday Aug. 26 without inventing an exact clock time.",
        "source_urls": [
            "https://www.diningwithmimi.com/recipe/easy-low-calorie-baked-salmon/",
            "https://mobilebayrunner.com/2017/08/",
        ],
        "notes": "Use as a dated Fairhope/Yacht Club-area positive. Do not infer a continuous shoreline boundary or an exact start/end time. Copyrighted images are not archived.",
    },
]


def main():
    doc = json.loads(EVENTS.read_text(encoding="utf-8"))
    events = doc.get("events")
    if not isinstance(events, list):
        raise SystemExit("event_history.json lacks events list")
    ids = [row.get("event_id") for row in events]
    if len(ids) != len(set(ids)):
        raise SystemExit("event_history.json already contains duplicate event IDs")
    added = []
    for row in ADDITIONS:
        if row["event_id"] not in ids:
            events.append(row)
            ids.append(row["event_id"])
            added.append(row["event_id"])
    events.sort(key=lambda x: (x.get("event_date_ct", "9999-99-99"), x.get("event_id", "")))
    doc["schema_version"] = "1.5"
    EVENTS.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "added": added, "event_count": len(events), "production_action": "NO_CHANGE"}, indent=2))


if __name__ == "__main__":
    main()

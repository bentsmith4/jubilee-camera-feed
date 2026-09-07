#!/usr/bin/env python3
"""Idempotently merge newly verified historical source leads into the canonical registry.

This script deliberately does not create Jubilee event labels from aggregate,
month-level, or agency-summary evidence. Exact event promotion remains a
separate reviewed step.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "historical_event_source_registry.json"

ADDITIONS = [
    {
        "source_id": "gulf_states_marine_fisheries_1957_alabama_jubilee_report",
        "type": "state_federal_fisheries_agency_meeting_report",
        "title": "1957 Gulf States Marine Fisheries Commission Minutes - Alabama report",
        "year": 1957,
        "url": "https://gulfcouncil.org/wp-content/uploads/M-1957-10.pdf",
        "priority": "P0",
        "status": "verified_primary_agency_report_event_dates_unresolved",
        "reported_event_period": "approximately prior year to October 1957",
        "reported_details": "Alabama reported several fish jubilees investigated during the past year: one near Bellefontaine on the western shore and several along the eastern shore near Daphne. Chemical analyses at Jubilee localities showed lower-than-normal oxygen and higher carbon dioxide; deeper water miles offshore sampled several hours later also showed low oxygen/high carbon dioxide. A fuller scientific report was said to be in preparation.",
        "use": "high-value lead for recovering 1956-1957 Daphne-area event dates and contemporaneous oxygen measurements; mechanism corroboration",
        "guardrail": "Do not create individual event rows from 'several' until exact dates/locations are recovered from the underlying report, field notes or contemporary press."
    },
    {
        "source_id": "baldwin_county_historical_jubilee_15yr_synthesis",
        "type": "county_archive_historical_synthesis",
        "title": "Eastern Shore Jubilee historical synthesis preserved by Baldwin County Archives",
        "url": "https://baldwincountyal.gov/docs/default-source/archives/archival-records/historical_society_1973-1982_part_9_of_10.pdf",
        "priority": "P0",
        "status": "verified_aggregate_and_month_level_evidence_not_individual_event_rows",
        "reported_event_period": "15-year record during the 1950s and 1960s",
        "reported_details": "The synthesis reports 11 June, 19 July, 25 August and 6 September Jubilees over a 15-year record; a good Jubilee in February 1959 south of Point Clear; eight Jubilees between July 6 and July 19, 1959; one all-night Jubilee in 1952; and no Jubilees reported in 1954.",
        "use": "constrain historical event recovery, seasonality and search targets; identify 1959 as a dense event cluster",
        "guardrail": "Aggregate/month-level counts are not individual training positives and the 1954 'no reports' statement is not a clean negative because observation effort is not quantified."
    },
    {
        "source_id": "alabama_archives_mobile_press_1959_02_16_point_clear",
        "type": "contemporaneous_newspaper_photo_archived_by_state_archive",
        "title": "Alice Wyllie and Mrs. Gordon Sawyer gigging flounders during a jubilee in Point Clear, Alabama",
        "archive": "Alabama Department of Archives and History, Alabama Media Group Collection",
        "record_date": "1959-02-16",
        "publication_date": "1959-02-16",
        "location": "Point Clear; Baldwin County synthesis independently places the February 1959 Jubilee south of Point Clear",
        "url": "https://alabamamosaic.org/vufind/Record/ADAHamg195596/Details",
        "priority": "P0",
        "status": "verified_contemporaneous_event_evidence_exact_event_day_requires_one_more_chronology_check",
        "use": "narrow February 1959 Point Clear event from month-level to a near-exact contemporaneous photo/publication date",
        "reported_details": "The archived Mobile Press image is dated/published February 16, 1959 and depicts Wyllie and Sawyer gigging flounders during a Point Clear Jubilee; caption reads 'Reaping Jubilee Harvest.'",
        "guardrail": "Do not assert the Jubilee occurred on February 16 solely because the photo/archive/publication is dated February 16; recover caption chronology or another contemporary item that ties the event itself to that day. Do not retain the copyrighted photograph."
    },
    {
        "source_id": "dining_with_mimi_2017_08_26_fairhope",
        "type": "first_person_local_blog_event_report",
        "title": "Fairhope Paddle Group Jubilee account",
        "event_date": "2017-08-26",
        "event_date_basis": "Saturday account plus independent Aug. 27 Mobile Bay Runner corroboration and eclipse-week calendar context",
        "location": "Fairhope shoreline toward Fairhope Yacht Club",
        "url": "https://www.diningwithmimi.com/recipe/easy-low-calorie-baked-salmon/",
        "priority": "P0",
        "status": "verified_event_source_promoted",
        "use": "dated Fairhope/Yacht Club-area positive; biological and human-search/contact evidence",
        "reported_details": "First-person Saturday paddle account says the Jubilee had already started; shoreline adults/children had nets, buckets and ice chests; dense birds and multiple species including flounder, crabs, shrimp, stingray, catfish and schools of fish were observed.",
        "guardrail": "Do not infer exact event start/end or continuous shoreline extent; copyrighted imagery is not archived."
    },
    {
        "source_id": "gulf_shores_pier_fishing_2012_jubilee_thread",
        "type": "public_local_fishing_forum_multi_participant_observation_effort",
        "title": "Jubilee Thread",
        "year": 2012,
        "url": "https://www.gulfshorespierfishing.com/f27/jubilee-thread-4211/",
        "priority": "P0",
        "status": "verified_observation_effort_and_near_miss_evidence_conflicting_local_outcomes",
        "use": "historical Fairhope/Fly Creek search-effort, near-miss and possible localized-event evidence",
        "reported_details": "Participants explicitly planned predawn Fly Creek/Fairhope checks, described baby flounder/crabs at the water edge on one check, a 'nothing' result on another, and a possible small Fairhope Pier event reported by another participant.",
        "guardrail": "Keep each participant/time/location scoped; conflicting forum observations do not collapse into either a clean negative or a confirmed cell-wide positive."
    },
    {
        "source_id": "1819_news_2024_06_12_point_clear_zundel_social_chain",
        "type": "contemporaneous_news_relay_of_public_social_alerts_and_checks",
        "title": "Jubilee brings sealife to surface near Grand Hotel Wednesday sunrise",
        "event_date": "2024-06-12",
        "location": "Zundel Road / Point Clear near Grand Hotel",
        "url": "https://1819news.com/news/item/jubilee-brings-sealife-to-surface-near-grand-hotel-wednesday-sunrise",
        "priority": "P0",
        "status": "verified_event_and_observation_effort_source_chain",
        "use": "localized Point Clear positive plus contemporaneous cross-cell observation-effort evidence",
        "reported_details": "Report says first alerts were around 6 a.m.; public Facebook Jubilee-watch communities posted alerts/photos; a contemporaneous May Day Pier check reportedly found nothing.",
        "guardrail": "The May Day observation is a scoped weak-to-moderate negative for its checked area/time only, not a Daphne cell-wide clean negative. Social/news reposts deriving from one report must share an independence group."
    }
]


def main():
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = doc.get("sources")
    if not isinstance(sources, list):
        raise SystemExit("historical_event_source_registry.json lacks sources list")
    by_id = {row.get("source_id"): row for row in sources}
    added, updated = [], []
    for row in ADDITIONS:
        sid = row["source_id"]
        if sid in by_id:
            if by_id[sid] != row:
                by_id[sid].clear(); by_id[sid].update(row); updated.append(sid)
        else:
            sources.append(row); by_id[sid] = row; added.append(sid)

    # The 2017 lead is no longer unresolved after independent source recovery.
    old = by_id.get("mobile_bay_runner_2017_aug_mini_jubilee")
    if old:
        patch = {
            "event_window": "2017-08-26",
            "status": "verified_independent_corroboration_for_2017_08_26_fairhope_event",
            "use": "independent corroboration for the resolved Aug. 26, 2017 Fairhope/Yacht Club-area positive",
            "guardrail": "Mobile Bay Runner alone does not localize the exact shoreline; geographic precision comes from the independent Dining With Mimi first-person paddle account."
        }
        changed = False
        for key, value in patch.items():
            if old.get(key) != value:
                old[key] = value; changed = True
        if changed: updated.append(old["source_id"])

    targets = [
        "Recover Loesch 1960 primary event table/dates and locations rather than relying on secondary summaries of 37 events.",
        "Normalize May 1973 underlying dated DO stations/profiles and distinguish Jubilee-linked observations from generic hypoxia.",
        "Search Alabama Department of Archives and History / Mobile Press records for the other seven reported July 6-19, 1959 Jubilees and resolve the exact day of the February 1959 south-Point-Clear event.",
        "Trace 1956-1957 Daphne-area Gulf States Marine Fisheries Commission Jubilee investigations back to field notes/full report and exact dates.",
        "Trace the 2024 Point Clear report back to the original public Facebook alert/post metadata and independent contemporaneous reports.",
        "Recover the original WKRG July 24, 2025 resident-video report metadata and exact shoreline scope.",
        "Resolve the July 2013 I Cast In a Yak report before calibration use.",
        "Systematically search 2010-2026 indexed public social/news sources by summer date and shoreline cell.",
        "Search historical newspaper archives and Sea Grant/ADCNR/Alabama Marine Resources records for dated events before 2010.",
        "Build observation-effort-aware non-event controls rather than treating missing reports as negatives."
    ]
    doc["next_recovery_targets"] = targets
    doc["schema_version"] = "1.3"
    doc["retrieval_date"] = "2026-09-07"
    REGISTRY.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status":"complete","added":added,"updated":sorted(set(updated)),"source_count":len(sources)}, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Derive scoped historical human observation-effort/control candidates.

This is intentionally conservative: it never converts 'no report' to a
negative and it does not admit a clean training control unless the source
contains a known check, sufficiently bounded location/time, and no conflicting
positive within that checked scope.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "human_observation_recovery_20260907.json"
OUT = HERE / "historical_human_control_candidates.json"


def classify(row):
    role = row.get("evidence_role", "")
    if row.get("evidence_id") == "2024-06-12-may-day-reported-nothing":
        return {
            "candidate_status": "SCOPED_CONTROL_CANDIDATE_NOT_TRAINING_NEGATIVE",
            "negative_evidence_strength": row.get("negative_evidence_strength", "WEAK_TO_MODERATE"),
            "missing_before_training": [
                "exact check start/end time",
                "search duration and shoreline extent",
                "visibility/detectability basis",
                "tide/current phase matching to candidate positive/control windows"
            ],
            "reason": "Known contemporaneous May Day location check reported nothing, but effort/visibility/time bounds are incomplete."
        }
    if row.get("evidence_id") == "2012-06-21-fairhope-area-active-check-near-miss":
        return {
            "candidate_status": "NEAR_MISS_NOT_NEGATIVE",
            "negative_evidence_strength": "NONE",
            "missing_before_training": ["exact checked shoreline", "exact clock window"],
            "reason": "Active check observed baby flounder/crabs at the water edge; this is biologically suggestive near-miss evidence, not absence."
        }
    if row.get("evidence_id") == "2012-06-23-fly-creek-fairhope-search-window":
        return {
            "candidate_status": "AMBIGUOUS_EPISODE_NOT_CONTROL",
            "negative_evidence_strength": "NONE",
            "missing_before_training": ["participant-specific exact locations", "participant-specific exact times"],
            "reason": "Different participants reported both nothing and a possible small Fairhope Pier event; preserve heterogeneity rather than collapse to a label."
        }
    if "observation_effort" in role:
        return {
            "candidate_status": "OBSERVATION_EFFORT_ONLY",
            "negative_evidence_strength": "NONE",
            "missing_before_training": ["manual review"],
            "reason": "Known human observation effort exists but does not meet a clean-negative rule."
        }
    return None


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    candidates = []
    for row in source.get("records", []):
        decision = classify(row)
        if not decision:
            continue
        candidates.append({
            "control_candidate_id": "human_" + row["evidence_id"],
            "source_evidence_id": row["evidence_id"],
            "target_cell": row.get("shoreline_cell", "UNKNOWN"),
            "claimed_time_or_window": row.get("claimed_event_time"),
            "location": row.get("location"),
            "search_effort": row.get("search_effort") or row.get("human_search_behavior"),
            "first_person_or_repost": row.get("first_person_or_repost"),
            "independence_group": row.get("independence_group"),
            "source_url_or_id": row.get("post_url_or_id"),
            "source_confidence": row.get("confidence"),
            "season_match": "PENDING_FEATURE_JOIN",
            "clock_window_match": "PENDING_EXACT_TIME_RECOVERY",
            "tide_or_transport_match": "PENDING_FEATURE_JOIN",
            "camera_observation_effort": "UNKNOWN_HISTORICAL",
            "social_observation_effort": "KNOWN_SOURCE_SPECIFIC",
            "environmental_source_availability": "PENDING_HISTORICAL_JOIN",
            **decision,
        })
    doc = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Bias-aware candidates derived from known human checking; no row is a clean training negative yet.",
        "source": "model_data/human_observation_recovery_20260907.json",
        "candidate_count": len(candidates),
        "clean_training_negative_count": 0,
        "candidates": candidates,
        "promotion_rule": "A candidate becomes a matched control only after shoreline/time scope, detectability, season, predawn clock window, tide/current phase, and source availability are sufficiently established under matched_control_contract.json.",
        "guardrails": [
            "No report is never promoted to a negative.",
            "Conflicting observations remain ambiguous.",
            "Near-miss biology is not absence.",
            "A scoped negative applies only to the actually checked location/time.",
            "Post-event knowledge cannot leak into pre-event forecast features."
        ]
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":"complete","candidate_count":len(candidates),"clean_training_negative_count":0}, indent=2))


if __name__ == "__main__":
    main()

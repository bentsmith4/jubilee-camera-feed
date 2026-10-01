"""Reviewed post-dawn date-horizon maintenance for a frozen heuristic outlook.

This changes dates only. It never acquires evidence, estimates probability,
changes weights, clears alerts, or substitutes for model calibration.
"""
import argparse
import copy
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import bind_current_forecast as binding

ROOT = Path(__file__).resolve().parents[1]
CT = ZoneInfo("America/Chicago")
SEASON_START = (5, 18)
SEASON_END = (11, 14)
PROFILE_FIELDS = (
    "point_clear_range_percent",
    "point_clear_central_percent",
    "daphne_may_day_range_percent",
    "daphne_may_day_central_percent",
    "confidence",
)


def stamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    binding.require(parsed.utcoffset() is not None, "offset-aware --as-of is required")
    return parsed


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")


def profile(day):
    return tuple(day[field] for field in PROFILE_FIELDS)


def validate_source_horizon(snapshot):
    days = snapshot.get("outlook")
    binding.require(isinstance(days, list) and len(days) == binding.DAWN_HORIZON_DAYS,
                    "REVIEW_REQUIRED: zero-change Dawn roll-forward requires exactly three source outlook days")
    source_dates = [date.fromisoformat(day["date_ct"]) for day in days]
    binding.require(all(source_dates[index] == source_dates[0] + timedelta(days=index)
                        for index in range(len(source_dates))),
                    "REVIEW_REQUIRED: source outlook dates must be three consecutive days")
    profiles = [profile(day) for day in days]
    binding.require(all(item == profiles[0] for item in profiles[1:]),
                    "REVIEW_REQUIRED: daily heuristic profiles differ; numerical horizon reassessment required")
    return source_dates, profiles[0]


def build(snapshot_raw, forecast, as_of):
    binding.check(snapshot_raw, forecast)
    snapshot = json.loads(snapshot_raw)
    binding.probability_basis(snapshot)
    binding.validate_weights(snapshot)

    issue = binding.aware_time(snapshot["snapshot_time_ct"]).astimezone(CT)
    now = stamp(as_of) if isinstance(as_of, str) else as_of.astimezone(CT)
    binding.require(SEASON_START <= (issue.month, issue.day) <= SEASON_END,
                    "REVIEW_REQUIRED: Jubilee Dawn Forecast is outside May 18-November 14")
    binding.require(now.date() == issue.date(),
                    "REVIEW_REQUIRED: Dawn roll-forward requires a current-date snapshot in America/Chicago")
    source_dates, source_profile = validate_source_horizon(snapshot)
    targets = binding.expected_dawn_horizon(snapshot["snapshot_time_ct"])
    actual = [day["date_ct"] for day in snapshot["outlook"]]
    if actual == targets:
        binding.require_dawn_horizon(snapshot)
        return None

    updated = copy.deepcopy(snapshot)
    for day, target in zip(updated["outlook"], targets):
        day["date_ct"] = target

    binding.require(all(profile(day) == source_profile for day in updated["outlook"]),
                    "REVIEW_REQUIRED: zero-change profile mutated during horizon maintenance")
    updated["forecast_opportunity_status"] = (
        "Reviewed post-dawn three-day horizon roll-forward only; heuristic ranges, "
        "central estimates, confidence, zero production weights and strict alert gates are unchanged."
    )
    updated["probability_basis"]["reassessment_method"] = (
        "Post-dawn horizon-only review: moved an identical existing three-day frozen heuristic "
        "profile onto the current America/Chicago issue-date through issue-date+2 horizon. "
        "No numerical probability, confidence, production weight, UNKNOWN input or alert threshold changed."
    )
    updated["dawn_horizon_reassessment"] = {
        "status": "REVIEWED_ZERO_NUMERICAL_CHANGE",
        "source_dates": [item.isoformat() for item in source_dates],
        "target_dates": targets,
        "numeric_change_from_prior_snapshot": 0,
        "forecast_weights_changed": False,
        "alert_threshold_percent": 20,
        "alert_comparator": ">",
        "scope": "date horizon only; no sensing, calibration, event inference or alert clearing",
    }

    raw = encode(updated)
    projected = binding.project(raw)
    binding.require_dawn_horizon(updated)
    binding.require(projected["forecast_weights_changed"] is False, "Forecast weights changed")
    binding.require(projected["alert_threshold_percent"] == 20 and projected["alert_comparator"] == ">",
                    "Alert policy changed")
    binding.require(projected["alert_gates"] == forecast["alert_gates"], "Alert gates changed during horizon roll-forward")
    return raw, encode(projected)


def run(root, as_of=None):
    snapshot_path = root / binding.SNAPSHOT
    forecast_path = root / binding.FORECAST
    snapshot_raw = snapshot_path.read_bytes()
    forecast = json.loads(forecast_path.read_bytes())
    now = stamp(as_of) if as_of else datetime.now(CT)
    result = build(snapshot_raw, forecast, now)
    if result is None:
        binding.run(root, check_only=True, require_horizon=True)
        return "UNCHANGED: Dawn three-day horizon already current"
    new_snapshot, new_forecast = result
    snapshot_path.write_bytes(new_snapshot)
    forecast_path.write_bytes(new_forecast)
    binding.run(root, check_only=True, require_horizon=True)
    return "PASS: Dawn three-day horizon rolled forward with zero numerical change"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--as-of", help="Offset-aware review time; defaults to current America/Chicago time")
    args = parser.parse_args()
    try:
        print(run(args.root, args.as_of))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Dawn horizon roll-forward FAIL: " + str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

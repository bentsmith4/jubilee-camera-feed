"""Bind the frozen heuristic forecast to exact, already-assessed snapshot bytes.

This is a projection/consistency check, not sensing, recalibration, or a new
assessment at wall-clock time. Publish the snapshot and forecast in one commit.
"""
import argparse
import copy
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "model_data/current_state_snapshot.json"
FORECAST = "model_data/current_forecast.json"
PROBABILITY_TYPE = "HEURISTIC_JUDGMENT_NOT_EMPIRICALLY_CALIBRATED"
CELLS = (("point_clear", "Point Clear/Grand Hotel"), ("daphne_may_day", "Daphne/May Day"))
CT = ZoneInfo("America/Chicago")
DAWN_HORIZON_DAYS = 3


def expected_dawn_horizon(snapshot_time):
    issue_date = aware_time(snapshot_time).astimezone(CT).date()
    return [(issue_date + timedelta(days=offset)).isoformat() for offset in range(DAWN_HORIZON_DAYS)]


def require_dawn_horizon(snapshot):
    require(isinstance(snapshot.get("outlook"), list), "Snapshot outlook must be a list")
    actual = [item.get("date_ct") for item in snapshot["outlook"]]
    expected = expected_dawn_horizon(snapshot["snapshot_time_ct"])
    require(actual == expected,
            "Dawn forecast horizon must be exactly issue-date through issue-date+2 "
            f"in America/Chicago; expected {expected}, got {actual}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def aware_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "Snapshot time must have a UTC offset")
    return parsed


def validate_weights(value):
    if isinstance(value, dict):
        if "production_weight" in value:
            weight = value["production_weight"]
            require(type(weight) in (int, float) and weight == 0,
                    "Nonzero/invalid production_weight requires model review; cannot rebind")
        for item in value.values():
            validate_weights(item)
    elif isinstance(value, list):
        for item in value:
            validate_weights(item)


def probability_basis(snapshot):
    """Validate the writer contract; prose is not a no-change attestation."""
    basis = snapshot.get("probability_basis")
    require(isinstance(basis, dict),
            "probability_basis must be an object with probability_type, "
            "numeric_change_from_prior_snapshot and reassessment_method; "
            "repair the snapshot explicitly, do not coerce prose")
    for field in ("probability_type", "numeric_change_from_prior_snapshot", "reassessment_method"):
        require(field in basis, f"probability_basis.{field} is required")
    require(basis["probability_type"] == PROBABILITY_TYPE, "Expected frozen heuristic probability type")
    change = basis["numeric_change_from_prior_snapshot"]
    require(type(change) in (int, float) and math.isfinite(change) and change == 0,
            "probability_basis.numeric_change_from_prior_snapshot must be a numeric zero; "
            "numerical change requires forecast reassessment")
    method = basis["reassessment_method"]
    require(isinstance(method, str) and bool(method.strip()),
            "probability_basis.reassessment_method must be a nonempty string")
    return basis


def asos_parameters(station, admission):
    """Read the flat legacy map or the explicit production station envelope."""
    label = f"ASOS parameter_admission.{station}"
    require(isinstance(admission, dict) and bool(admission), f"{label} must be a nonempty object")
    wrapped = "parameters" in admission or "status" in admission
    if wrapped:
        require(set(admission) == {"status", "parameters"},
                f"{label} station envelope requires exactly status and parameters")
        parameters = admission["parameters"]
    else:
        parameters = admission
    require(isinstance(parameters, dict) and bool(parameters), f"{label}.parameters must be a nonempty object")
    for name, item in parameters.items():
        require(isinstance(item, dict) and item.get("value_status") in
                ("KNOWN", "TRACE", "UNKNOWN", "UNKNOWN_STALE"),
                f"{label}.{name} requires a valid value_status")
    if wrapped:
        status = admission["status"]
        require(status in ("KNOWN", "PARTIAL", "PARTIAL_FRESH", "UNKNOWN", "UNKNOWN_STALE"),
                f"{label}.status is invalid")
        known = [item["value_status"] in ("KNOWN", "TRACE") for item in parameters.values()]
        expected = "KNOWN" if all(known) else ("PARTIAL" if any(known) else "UNKNOWN")
        summary = {"UNKNOWN_STALE": "UNKNOWN", "PARTIAL_FRESH": "PARTIAL"}.get(status, status)
        require(summary == expected,
                f"{label}.status disagrees with parameter admission")
        if status == "UNKNOWN_STALE":
            require(all(item.get("admission_reason") == "STALE_AT_ISSUE_TIME" for item in parameters.values()),
                    f"{label}.status requires explicit stale parameter evidence")
    return parameters


def coverage(snapshot):
    def row(source):
        matches = [item for item in snapshot["input_rows"] if item["source"] == source]
        require(len(matches) == 1, f"Expected one snapshot input row for {source}")
        return matches[0]

    cameras = row("bentsmith4/jubilee-camera-feed status.json, burst_status.json and vision.json")["camera_health"]
    products = row("NOAA NGOFS2 repository manifests")["products"]
    river = row("USGS NWIS lower-river forcing manifest")["series"]
    asos = row("NOAA/NWS ASOS KBFM and KMOB")["parameter_admission"]
    require(isinstance(asos, dict) and bool(asos), "ASOS parameter_admission must be a nonempty object")
    statuses = {}
    for station, admission in sorted(asos.items()):
        parameters = asos_parameters(station, admission)
        known = [item["value_status"] == "KNOWN" for item in parameters.values()]
        statuses[station] = ("complete" if all(known) else "partial") if any(known) else "UNKNOWN"
    asos_summary = "; ".join(f"{station} {status}" for station, status in statuses.items()) or "UNKNOWN"
    if len(set(statuses.values())) == 1:
        asos_summary = "/".join(statuses) + " " + next(iter(statuses.values()))
    return {
        "private_camera_metadata_pass": cameras["private_metadata_pass"],
        "private_cameras_expected": cameras["expected_private_cameras"],
        "ngofs2_products": {name: item["admitted_status"] for name, item in products.items()},
        "fresh_river_series": sum(item["fresh"] is True and item["value_status"].startswith("KNOWN") for item in river),
        "asos_stations": asos_summary,
    }


def project(snapshot_bytes):
    """Deterministic projection; never replace UNKNOWN or recalculate probabilities."""
    snapshot = json.loads(snapshot_bytes)
    require(isinstance(snapshot, dict), "Snapshot must be a JSON object")
    basis = probability_basis(snapshot)
    reconciliation = snapshot["reconciliation"]
    require(snapshot["forecast_weights_changed"] is False, "Forecast weights changed; cannot rebind")
    require(reconciliation["alert_threshold_percent"] == 20 and reconciliation["alert_comparator"] == ">",
            "Alert policy must remain strict >20%")
    require(re.fullmatch(r"[0-9a-f]{40}", reconciliation["input_commit_sha"]) is not None,
            "Invalid snapshot input_commit_sha")
    require(aware_time(snapshot["snapshot_time_ct"]) == aware_time(reconciliation["as_of_utc"]),
            "Snapshot and reconciliation issue times differ")
    validate_weights(snapshot)

    outlooks = []
    dates = set()
    triggered = {prefix: False for prefix, _ in CELLS}
    require(bool(snapshot["outlook"]), "No assessed outlooks in snapshot")
    for day in snapshot["outlook"]:
        date.fromisoformat(day["date_ct"])
        require(day["date_ct"] not in dates, "Duplicate outlook date")
        dates.add(day["date_ct"])
        for prefix, cell in CELLS:
            span = day[prefix + "_range_percent"]
            match = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", span)
            require(match is not None, "Invalid assessed probability range")
            low, high = map(float, match.groups())
            central = day[prefix + "_central_percent"]
            require(type(central) in (int, float) and math.isfinite(central)
                    and 0 <= low <= central <= high <= 100, "Invalid assessed probability bounds")
            # Preserve the existing gate's central-estimate basis, including 20 != >20.
            triggered[prefix] |= central > 20
            outlooks.append({
                "cell": cell,
                "forecast_window": {"date_ct": day["date_ct"], "scope": "existing dated outlook; intraday validity window was not specified by the prior heuristic"},
                "range_percent": span,
                "central_percent": central,
                "confidence": day["confidence"],
            })
    gates = snapshot["alert_gates"]
    for prefix, _ in CELLS:
        require(gates[prefix + "_over_20_percent"] is triggered[prefix], "Snapshot opportunity gate disagrees with strict >20%")
    require(all(type(value) is bool for value in gates.values()), "Alert gates must be explicit booleans")
    notification = any((triggered["point_clear"], triggered["daphne_may_day"],
                        gates["direct_event_evidence_present"], gates["material_critical_input_fault"]))
    require(snapshot["notification_condition_met"] is notification
            and gates["notification_suppressed"] is (not notification), "Snapshot notification gates disagree")
    return {
        "schema_version": "1.0",
        "issue_time": snapshot["snapshot_time_ct"],
        "model_version": "expert_policy_baseline / model_policy_v2.1",
        "probability_type": PROBABILITY_TYPE,
        "input_snapshot_file": SNAPSHOT,
        "input_snapshot_hash": hashlib.sha256(snapshot_bytes).hexdigest(),
        # This is the snapshot's upstream evidence commit, not its publication commit.
        "input_commit_sha": reconciliation["input_commit_sha"],
        "forecast_weights_changed": False,
        "alert_threshold_percent": 20,
        "alert_comparator": ">",
        "forecast_status": "FROZEN_HEURISTIC_REASSESSED_NO_NUMERICAL_CHANGE",
        "method": basis["reassessment_method"],
        "data_coverage": coverage(snapshot),
        "missing_inputs": copy.deepcopy(snapshot["known_unknowns"]),
        "outlooks": outlooks,
        "alert_gates": copy.deepcopy(gates),
        "notification_condition_met": notification,
        "later_verification": "PENDING; no future outcome or next-dawn acceptance claimed",
    }


def check(snapshot_bytes, forecast):
    expected = project(snapshot_bytes)
    differences = sorted(key for key in expected.keys() | forecast.keys()
                         if key not in expected or key not in forecast or expected[key] != forecast[key])
    require(not differences, "Forecast/snapshot mismatch: " + ", ".join(differences)
            + ". Run python model_data/bind_current_forecast.py and commit both files together.")


def run(root, check_only=False, require_horizon=False):
    snapshot_path, forecast_path = root / SNAPSHOT, root / FORECAST
    snapshot_bytes = snapshot_path.read_bytes()
    if require_horizon:
        require_dawn_horizon(json.loads(snapshot_bytes))
    if check_only:
        check(snapshot_bytes, json.loads(forecast_path.read_bytes()))
    else:
        forecast = project(snapshot_bytes)
        # Rebinding is not permission to silently replace already assessed ranges.
        previous = json.loads(forecast_path.read_bytes())
        require(previous["outlooks"] == forecast["outlooks"],
                "Forecast outlooks differ: assess and update them explicitly before rebinding")
        require(snapshot_path.read_bytes() == snapshot_bytes, "Snapshot changed during binding; retry")
        temporary = forecast_path.with_suffix(".json.tmp")
        try:
            temporary.write_bytes((json.dumps(forecast, indent=2, allow_nan=False) + "\n").encode("utf-8"))
            temporary.replace(forecast_path)
        finally:
            temporary.unlink(missing_ok=True)
        check(snapshot_path.read_bytes(), json.loads(forecast_path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Read-only; fail if the forecast is not the snapshot projection")
    parser.add_argument("--require-dawn-horizon", action="store_true",
                        help="Require issue-date through issue-date+2 outlook coverage for Dawn Brief publication")
    args = parser.parse_args()
    try:
        run(args.root, args.check, args.require_dawn_horizon)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Forecast binding FAIL: {error}", file=sys.stderr)
        return 1
    print("Forecast binding PASS: exact snapshot hash, issue time, input commit, outlooks and alert gates match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

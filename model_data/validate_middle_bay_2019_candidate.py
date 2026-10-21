"""Research-only pre-ingest QC for NCEI accession 0224293 candidate rows.

No native archive payload is present in this repository.  This validator does
not ingest data, derive bottom DO, or supply forecast predictors.  It explicitly
separates historical scientific-row admissibility from forecast-time availability.
"""
from datetime import date, datetime
import math
import re

ACCESSION = "0224293"
HYDRO_START = date(2019, 1, 1)
HYDRO_LAST = date(2019, 7, 3)
VALID_UNITS = {
    "dissolved_oxygen_mg_l": "mg/L",
    "dissolved_oxygen_percent": "%",
    "salinity": "psu",
    "water_temperature": "degC",
}
HASH = re.compile(r"^[a-f0-9]{64}$")
ORIGINAL_SHA256 = "49e04d4903d6f6edc4f6bbbc91e9b7e81a6c6ed560318a0621d1d9c454c5e7fb"


def _instant(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo is not None and d.utcoffset() is not None else None


def evaluate_candidate(row, issue_time=None):
    """Return explicit scientific/as-of gates; never guess missing source fields.

    Candidate is a *prospective normalized schema*, not the undocumented native
    NOAA column layout.  A 'good' QC value comes from the NCEI source metadata,
    not from another provider's QARTOD integer convention.
    """
    errors = []
    if row.get("native_schema_verified") is not True:
        errors.append("native_schema_not_verified")
    if row.get("source_time_basis_verified") is not True:
        errors.append("source_time_basis_not_verified")
    if row.get("sensor_deployment_verified") is not True:
        errors.append("sensor_deployment_not_verified")
    if row.get("stationid") != "188":
        errors.append("wrong_station_or_missing_station")
    if row.get("accession") != ACCESSION or row.get("kind") != "hydro":
        errors.append("wrong_source_or_stream")
    obs = _instant(row.get("observed_at"))
    if obs is None:
        errors.append("observation_timezone_unknown")
    elif not HYDRO_START <= obs.date() <= HYDRO_LAST:
        errors.append("outside_verified_hydro_period")
    parameter = row.get("parameter")
    if parameter not in VALID_UNITS:
        errors.append("unapproved_or_unknown_parameter")
    elif row.get("units") != VALID_UNITS[parameter]:
        errors.append("units_unverified")
    if str(row.get("native_qc")) != "3":
        errors.append("not_native_qc_good")
    val = row.get("value")
    if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
        errors.append("value_unusable")
    else:
        if parameter == "dissolved_oxygen_mg_l" and not 0 <= val <= 20:
            errors.append("do_mg_l_outside_native_range")
        if parameter == "dissolved_oxygen_percent" and not 0 <= val <= 200:
            errors.append("do_percent_outside_native_range")
        if parameter == "salinity" and not 0 <= val <= 40:
            errors.append("salinity_outside_native_range")
        if parameter == "water_temperature" and not -5 <= val <= 45:
            errors.append("temperature_outside_native_range")
    if not (isinstance(row.get("sensor_height_above_bed_m"), (int, float)) and
            not isinstance(row.get("sensor_height_above_bed_m"), bool) and
            math.isfinite(row.get("sensor_height_above_bed_m")) and
            row.get("sensor_height_above_bed_m") >= 0):
        errors.append("sensor_height_not_verified")
    if not row.get("depth_datum"):
        errors.append("depth_datum_unknown")
    if not isinstance(row.get("raw_sha256"), str) or not HASH.fullmatch(row["raw_sha256"]):
        errors.append("raw_hash_absent")
    elif row["raw_sha256"] != ORIGINAL_SHA256:
        errors.append("wrong_original_source_hash")
    if not row.get("raw_file_id"):
        errors.append("raw_file_identity_absent")
    available = _instant(row.get("available_at"))
    if available is None:
        errors.append("availability_timezone_unknown")
    elif obs is not None and available < obs:
        errors.append("availability_before_observation")
    scientific = len(errors) == 0
    issue = _instant(issue_time)
    forecast_eligible = scientific and issue is not None and available <= issue
    return {
        "scientific_qc_admissible": scientific,
        "forecast_time_eligible": forecast_eligible,
        "reasons": errors + ([] if issue is None or not scientific or forecast_eligible
                               else ["not_available_as_of_issue"]),
        "source_class": "CENTRAL_BAY_HISTORICAL_HYDROGRAPHY_NOT_SHORELINE_BOTTOM_CURRENT",
        "production_weight": 0,
        "point_clear_bottom_state_eligible": False,
        "earth_frame_current_eligible": False,
    }

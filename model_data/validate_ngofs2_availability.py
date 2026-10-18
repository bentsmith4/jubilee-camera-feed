"""Accept retrieval outages while rejecting NGOFS2 parser and validation failures."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCTS = {
    "ngofs2_point_clear_nowcast": ["ngofs2_point_clear_nowcast_normalized.csv"],
    "ngofs2_point_clear_forecast": ["ngofs2_point_clear_forecast_normalized.csv"],
    "ngofs2_mobile_bay_named_stations_nowcast": ["ngofs2_mobile_bay_named_stations_nowcast_normalized.csv"],
    "ngofs2_mobile_bay_named_stations_forecast": ["ngofs2_mobile_bay_named_stations_forecast_normalized.csv"],
    "ngofs2_shoreline_grid": ["ngofs2_shoreline_grid_normalized.csv", "ngofs2_shoreline_grid_features.csv"],
}

# NetCDF NC_EDAPSVC (-70), including netCDF4's OSError form at dataset open.
# The bare RuntimeError occurs during a lazy remote variable read (run
# 36374092683). Match the whole message, not arbitrary DAP/NetCDF substrings:
# generic libcurl/I/O errors and malformed responses can be client/data defects.
# Reference: https://docs.unidata.ucar.edu/netcdf-c/current/nc-error-codes.html
NETCDF_DAP_SERVER_ERROR = re.compile(
    r"(?:\[Errno -70\] )?NetCDF: DAP server error"
    r"(?:: 'https://opendap\.co-ops\.nos\.noaa\.gov/thredds/dodsC/NOAA/NGOFS2/MODELS/[^\s']+')?"
)
GRID_FAILURE_CONTRACT = "ngofs2_grid_retrieval_v1"
GRID_SOURCE_URL = re.compile(
    r"https://opendap\.co-ops\.nos\.noaa\.gov/thredds/dodsC/NOAA/NGOFS2/MODELS/"
    r"\d{4}/\d{2}/\d{2}/ngofs2\.t\d{2}z\.\d{8}\.regulargrid\.[nf]\d{3}\.nc"
)


def grid_retrieval_failure(attempt):
    """Recognize only confirmed remote access failures, never parser text hints.

    NC_ENOTFOUND (-90) and NC_EDAPSVC (-70) are provider retrieval failures at
    these remote boundaries. Generic DAP, curl, I/O and malformed responses
    remain fatal because they can indicate client/data defects.
    """
    if not isinstance(attempt, dict) or attempt.get("stage") not in {
            "reference_open", "reference_read", "slice_open", "slice_read"}:
        return False
    url = attempt.get("source_url")
    if not isinstance(url, str) or GRID_SOURCE_URL.fullmatch(url) is None:
        return False
    error_type, error = attempt.get("error_type"), attempt.get("error")
    if error_type == "HTTPError":
        return attempt.get("http_status") in {404, 408, 429, 500, 502, 503, 504}
    if error_type not in {"RuntimeError", "OSError"}:
        return False
    # Full messages and the exact remote URL are retained, without truncation.
    return any(error == prefix + message + suffix
               for code, message in ((-70, "NetCDF: DAP server error"),
                                     (-90, "NetCDF: file not found"))
               for prefix in ("", f"[Errno {code}] ")
               for suffix in ("", f": '{url}'"))


def retrieval_outage(manifest):
    attempts = manifest.get("retrieval_attempts")
    if "failure_contract" in manifest or manifest.get("error_type") == "GridRetrievalError":
        # New grid manifests must never fall through to legacy text heuristics.
        return (manifest.get("failure_contract") == GRID_FAILURE_CONTRACT
                and manifest.get("error_type") == "GridRetrievalError"
                and isinstance(attempts, list) and bool(attempts)
                and all(grid_retrieval_failure(a) for a in attempts))
    if manifest.get("error_type") == "StationRetrievalError":
        return (isinstance(attempts, list) and bool(attempts)
                and all(isinstance(a, dict) and a.get("stage") == "http_download"
                        and ((a.get("error_type") == "HTTPError"
                              and a.get("http_status") in {404, 408, 429, 500, 502, 503, 504})
                             or a.get("error_type") in {"URLError", "TimeoutError"})
                        for a in attempts))
    if manifest.get("error_type") == "RetrievalOpenError":
        return (isinstance(attempts, list) and bool(attempts)
                and all(isinstance(a, dict)
                        and a.get("error_type") in {"RuntimeError", "OSError"}
                        and NETCDF_DAP_SERVER_ERROR.fullmatch(str(a.get("error", ""))) is not None
                        for a in attempts))
    error = str(manifest.get("error", ""))
    return (manifest.get("error_type") == "RetrievalTimeout"
            or (manifest.get("error_type") in {"RuntimeError", "OSError"}
                and NETCDF_DAP_SERVER_ERROR.fullmatch(error) is not None)
            or "HTTP 503" in error or "503 Service Unavailable" in error
            or error.startswith(("Unable to open any recent NGOFS2 station dataset:",
                                 "No recent NGOFS2 ")) and "file opened:" in error
            or error.startswith("No recent NGOFS2 regular-grid ") and "reference file opened:" in error)


def validate(root=HERE):
    summary = {}
    for name, csv_names in PRODUCTS.items():
        path = root / f"{name}_manifest.json"
        if not path.exists():
            raise RuntimeError(f"Missing NGOFS2 manifest: {path.name}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete":
            summary[name] = "complete"
            continue
        if manifest.get("status") != "failed" or not retrieval_outage(manifest):
            raise RuntimeError(f"NGOFS2 validation or parser failure: {path.name}: {manifest.get('error_type')}")
        manifest["status"] = "unavailable"
        manifest["production_action"] = "NO_CURRENT_GUIDANCE"
        # A subprocess deadline is not evidence that NOAA itself failed.
        # Historical timeout manifests lack the new bounded-run diagnostic fields.
        manifest["availability_reason"] = ("retrieval_timeout_cause_unresolved"
                                           if manifest.get("error_type") == "RetrievalTimeout"
                                           else "station_http_retrieval_unavailable_cause_unresolved"
                                           if manifest.get("error_type") == "StationRetrievalError"
                                           else "upstream_retrieval_failure")
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if name == "ngofs2_point_clear_nowcast":
            (root / "ngofs2_point_clear_manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for csv_name in csv_names:
            (root / csv_name).unlink(missing_ok=True)
        summary[name] = "unavailable"
    (root / "ngofs2_availability.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))

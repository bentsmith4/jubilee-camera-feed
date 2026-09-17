"""Accept retrieval outages while rejecting NGOFS2 parser and validation failures."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCTS = {
    "ngofs2_point_clear_nowcast": ["ngofs2_point_clear_nowcast_normalized.csv"],
    "ngofs2_point_clear_forecast": ["ngofs2_point_clear_forecast_normalized.csv"],
    "ngofs2_mobile_bay_named_stations_nowcast": ["ngofs2_mobile_bay_named_stations_nowcast_normalized.csv"],
    "ngofs2_mobile_bay_named_stations_forecast": ["ngofs2_mobile_bay_named_stations_forecast_normalized.csv"],
    "ngofs2_shoreline_grid": ["ngofs2_shoreline_grid_normalized.csv", "ngofs2_shoreline_grid_features.csv"],
}


def retrieval_outage(manifest):
    error = str(manifest.get("error", ""))
    return ("HTTP 503" in error or "503 Service Unavailable" in error
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
        manifest["availability_reason"] = "upstream_retrieval_failure"
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

"""Stage only outputs whose producing steps completed in this sensing run.

The workflow passes step *outcomes*, not conclusions: continue-on-error must not
turn a failed producer into permission to publish its files. NGOFS2 is admitted
as a group only after the existing availability validator accepts every product.
"""
import json
import os
from pathlib import Path
import subprocess


RESEARCH_REFS = {"main", "upgrade/top5-gaps-round2-20260906"}


def publication_paths(steps, ref):
    """Return the existing public allowlist, restricted to successful producers."""
    paths = []

    def include(step, *names):
        if steps.get(step, {}).get("outcome") == "success":
            paths.extend("model_data/" + name for name in names)

    include("regression", "upgrade_test_report.json")
    include("audit", "sensing_audit.json")
    include("river", "river_forcing_manifest.json", "public_archive/usgs")
    include("asos", "asos_weather_manifest.json", "asos_weather_normalized.json",
            "current_asos_weather.json", "public_archive/asos")
    include("noaa_water_level", "noaa_water_level_manifest.json", "noaa_water_level_normalized.json",
            "current_noaa_water_level.json", "public_archive/coops")
    include("weeks_bay", "weeks_bay_realtime_manifest.json", "public_archive/ndbc")
    include("readiness", "upgrade_readiness.json", "coverage_snapshot.json")
    include("ngofs2_validation", "ngofs2_point_clear_manifest.json",
            "ngofs2_point_clear_nowcast_manifest.json", "ngofs2_point_clear_forecast_manifest.json",
            "ngofs2_availability.json", "public_archive/ngofs2_subset",
            "public_archive/ngofs2_named_station_subset", "public_archive/ngofs2_shoreline_grid_subset")
    if ref in RESEARCH_REFS:
        include("history", "event_history.json")
        include("historical_diagnostic", "historical_recovery_status.json")
        include("registry", "ongoing_source_registry_20260906.json")
        include("weeks_bay", "weeks_bay_realtime_normalized.csv")
        include("ngofs2_validation", "ngofs2_point_clear_nowcast_normalized.csv",
                "ngofs2_point_clear_forecast_normalized.csv",
                "ngofs2_mobile_bay_named_stations_nowcast_manifest.json",
                "ngofs2_mobile_bay_named_stations_forecast_manifest.json",
                "ngofs2_mobile_bay_named_stations_nowcast_normalized.csv",
                "ngofs2_mobile_bay_named_stations_forecast_normalized.csv",
                "ngofs2_shoreline_grid_manifest.json", "ngofs2_shoreline_grid_normalized.csv",
                "ngofs2_shoreline_grid_features.csv")
        include("main_pass", "griidc_main_pass_20160419_manifest.json",
                "griidc_main_pass_20160419_normalized.csv", "public_archive/griidc_main_pass_20160419")
    if ref == "upgrade/sensing-audit-20260906":
        include("water_quality", "water_quality_ingest_manifest.json", "water_quality_backtest.json",
                "public_archive/wqp")
    return paths


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def check_archive_capacity(root):
    """Fail closed on invalid policy; preserve the shared warning and hard stop."""
    root = Path(root)
    policy = json.loads((root / "model_data/data_retention_policy.json").read_text())
    classes = [item for item in policy["storage_classes"]
               if item["class"] == "raw_public_environmental_observation"]
    if len(classes) != 1:
        raise ValueError("Expected exactly one public environmental archive policy")
    soft = classes[0]["public_git_soft_budget_bytes"]
    hard = classes[0]["public_git_hard_budget_bytes"]
    if type(soft) is not int or type(hard) is not int or not 0 < soft <= hard:
        raise ValueError("Invalid public archive capacity limits")
    size = sum(p.stat().st_size for p in (root / "model_data/public_archive").rglob("*") if p.is_file())
    capacity = (f"Public archive: {size:,} bytes; migration threshold "
                f"{soft:,}; hard ceiling {hard:,}; "
                f"remaining {max(0, hard - size):,} bytes.")
    print(capacity)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("\n### Public sensing archive capacity\n\n" + capacity + "\n")
            if size > soft:
                out.write("\nJ04: verified object-storage migration remains required. "
                          "This recovery ceiling is finite; no history was deleted.\n")
    if size > hard:
        raise RuntimeError("Public Git archive budget exceeded. Preserve the artifact and migrate to verified object storage; do not delete history.")
    if size > soft:
        print("::warning title=J04 public archive migration required::" + capacity +
              " Preserve all history and migrate to verified object storage before the hard ceiling.")


def stage_water_quality(root):
    """Stage weekly diagnostics only after all preceding workflow steps succeed."""
    root = Path(root)
    check_archive_capacity(root)
    if git(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("Water-quality publication requires an empty index")
    archive = "model_data/public_archive/wqp"
    if git(root, "diff", "HEAD", "--name-only", "--", archive):
        raise RuntimeError(f"Public archives are append-only: {archive}")
    git(root, "add", "--", "model_data/water_quality_ingest_manifest.json",
        "model_data/water_quality_backtest.json", "model_data/water_quality_run_summary.json", archive)


def stage(root, steps, ref):
    root = Path(root)
    check_archive_capacity(root)
    if git(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("Sensing publication requires an empty index")
    if steps.get("regression", {}).get("outcome") != "success":
        return
    paths = publication_paths(steps, ref)
    for path in paths:
        if "/public_archive/" in path and git(root, "diff", "HEAD", "--name-only", "--", path):
            raise RuntimeError(f"Public archives are append-only: {path}")
    for path in paths:
        # Include tracked deletions: validated NGOFS2 outages must remove stale
        # current CSVs, while immutable archives may only gain new files.
        if (root / path).exists() or git(root, "ls-files", "--", path):
            git(root, "add", "-A", "--", path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--water-quality", action="store_true")
    mode.add_argument("--check-archive", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.water_quality:
        stage_water_quality(root)
    elif args.check_archive:
        check_archive_capacity(root)
    else:
        stage(root, json.loads(os.environ["SENSING_STEPS_JSON"]), os.environ["REF_NAME"])

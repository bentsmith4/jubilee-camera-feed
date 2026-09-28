"""Stage only outputs whose producing steps completed in this sensing run.

The workflow passes step *outcomes*, not conclusions: continue-on-error must not
turn a failed producer into permission to publish its files. NGOFS2 is admitted
as a group only after the existing availability validator accepts every product.
"""
import json
import os
from pathlib import Path
import subprocess


ARCHIVE_BUDGET = 250_000_000
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


def stage(root, steps, ref):
    root = Path(root)
    size = sum(p.stat().st_size for p in (root / "model_data/public_archive").rglob("*") if p.is_file())
    if size > ARCHIVE_BUDGET:
        raise RuntimeError("Public Git archive budget exceeded. Preserve the artifact and migrate to verified object storage; do not delete history.")
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
    stage(Path(__file__).resolve().parents[1], json.loads(os.environ["SENSING_STEPS_JSON"]),
          os.environ["REF_NAME"])

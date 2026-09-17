"""Bound an external NGOFS2 retrieval so the sensing job can report unavailable."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCTS = {
    "point_clear_nowcast": ("ingest_ngofs2_point_clear.py", ["--cast", "nowcast"], "ngofs2_point_clear_nowcast_manifest.json", 480),
    "point_clear_forecast": ("ingest_ngofs2_point_clear.py", ["--cast", "forecast"], "ngofs2_point_clear_forecast_manifest.json", 480),
    "named_stations_nowcast": ("ingest_ngofs2_mobile_bay_named_stations.py", ["--cast", "nowcast"], "ngofs2_mobile_bay_named_stations_nowcast_manifest.json", 480),
    "named_stations_forecast": ("ingest_ngofs2_mobile_bay_named_stations.py", ["--cast", "forecast"], "ngofs2_mobile_bay_named_stations_forecast_manifest.json", 480),
    "shoreline_grid": ("ingest_ngofs2_shoreline_grid.py", ["--casts", "nowcast,forecast"], "ngofs2_shoreline_grid_manifest.json", 720),
}


def run(product, root=HERE, runner=subprocess.run):
    script, args, manifest_name, seconds = PRODUCTS[product]
    try:
        return runner([sys.executable, str(root / script), *args], cwd=root, timeout=seconds).returncode
    except subprocess.TimeoutExpired:
        manifest = {
            "status": "failed", "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "evidence_class": "MODEL", "production_action": "NO_CHANGE",
            "error_type": "RetrievalTimeout", "error": f"NGOFS2 retrieval exceeded {seconds} seconds",
        }
        (root / manifest_name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if product == "point_clear_nowcast":
            (root / "ngofs2_point_clear_manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"NGOFS2 {product} retrieval timed out after {seconds} seconds", file=sys.stderr)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("product", choices=PRODUCTS)
    args = parser.parse_args()
    raise SystemExit(run(args.product))

"""Resolve only regenerable sensing publication conflicts during a rebase.

The caller rebases an already producer-gated commit in a clean worktree. In a
rebase, --ours is the upstream state. Keep that registry (including research
metadata), then reapply ingestion-derived fields from the replayed manifests.
Any other conflict, failed producer gate, or reconciliation error must stop the
publication; never choose one entire registry at the expense of the other.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from stage_sensing_outputs import publication_paths


AUDIT = "model_data/sensing_audit.json"
REGISTRY = "model_data/ongoing_source_registry_20260906.json"


def resolve(root, steps, ref):
    root = Path(root)
    conflicts = set(subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=U", "-z"], cwd=root
    ).decode().split("\0")) - {""}
    allowed = {AUDIT, REGISTRY} & set(publication_paths(steps, ref))
    if (not conflicts or steps.get("regression", {}).get("outcome") != "success"
            or not conflicts <= allowed):
        raise RuntimeError(f"Unexpected or ungated publish conflict(s): {sorted(conflicts)}")

    # Validate the whole conflict set before touching anything. In particular,
    # conflicting manifests, archives and source code are never auto-resolved.
    for path in sorted(conflicts):
        subprocess.run(["git", "checkout", "--ours", "--", path], cwd=root, check=True)
    if REGISTRY in conflicts:
        subprocess.run([sys.executable, "model_data/reconcile_source_registry.py"],
                       cwd=root, check=True)
    subprocess.run(["git", "add", "--", *sorted(conflicts)], cwd=root, check=True)
    print("Resolved sensing publication conflicts from upstream state:", sorted(conflicts))


if __name__ == "__main__":
    resolve(Path(__file__).resolve().parents[1],
            json.loads(os.environ["SENSING_STEPS_JSON"]), os.environ["REF_NAME"])

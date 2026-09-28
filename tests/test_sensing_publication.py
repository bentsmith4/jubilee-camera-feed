"""Offline publication regressions, including a real mixed-success Git push."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "model_data" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load("stage_sensing_outputs")
validator = load("validate_ngofs2_availability")
WORKFLOW = (ROOT / ".github/workflows/sensing_quality.yml").read_text()
PUBLISH_STEP = WORKFLOW.split("      - name: Persist allowlisted public archives and audit records\n")[1].split("\n      - name:")[0]
BASH = shutil.which("bash") or ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else None)


def outcomes(**values):
    return {name: {"outcome": value} for name, value in values.items()}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Publication test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.write("baseline.txt", "baseline\n")
        self.write("model_data/stage_sensing_outputs.py", (ROOT / "model_data/stage_sensing_outputs.py").read_text())
        for path in publisher.publication_paths(outcomes(**{name: "success" for name in (
                "regression", "audit", "river", "weeks_bay", "readiness", "ngofs2_validation",
                "history", "historical_diagnostic", "registry", "main_pass")}), "main"):
            if "/public_archive/" in path:
                self.write(path + "/old.gz", "immutable archive\n")
            elif "_manifest.json" in path:
                self.write(path, json.dumps({"status": "complete"}))
            else:
                self.write(path, "old\n")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")

    def write(self, path, content):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.STDOUT).decode().strip()

    def staged(self):
        return set(self.git("diff", "--cached", "--name-only").splitlines())

    def test_workflow_uses_outcomes_after_failure_without_masking_validation(self):
        self.assertIn("if: ${{ !cancelled() && steps.regression.outcome == 'success' }}", PUBLISH_STEP)
        self.assertIn("SENSING_STEPS_JSON: ${{ toJSON(steps) }}", PUBLISH_STEP)
        gate = WORKFLOW.split("      - name: Allow upstream NGOFS2 outages but reject parser failures\n")[1].split("      - name:")[0]
        self.assertIn("id: ngofs2_validation", gate)
        self.assertNotIn("continue-on-error", gate)
        # Every producer referenced by the allowlist is wired to a workflow ID.
        for name in ("regression", "audit", "river", "weeks_bay", "readiness", "ngofs2_validation",
                     "history", "historical_diagnostic", "registry", "main_pass", "water_quality"):
            self.assertIn(f"        id: {name}\n", WORKFLOW)

    def test_failed_skipped_or_missing_producers_cannot_stage_outputs(self):
        self.write("model_data/river_forcing_manifest.json", "failed\n")
        self.write("model_data/public_archive/usgs/partial.gz", "partial\n")
        self.write("model_data/weeks_bay_realtime_manifest.json", "partial\n")
        self.write("model_data/sensing_audit.json", "unfinished\n")
        steps = outcomes(regression="success", river="failure", weeks_bay="skipped")
        steps["river"]["conclusion"] = "success"  # continue-on-error
        publisher.stage(self.root, steps, "main")
        self.assertEqual(self.staged(), set())

    def test_regression_failure_blocks_publication(self):
        self.write("model_data/sensing_audit.json", "new audit\n")
        publisher.stage(self.root, outcomes(regression="failure", audit="success"), "main")
        self.assertEqual(self.staged(), set())

    def test_missing_partial_and_invalid_ngofs2_cannot_leak_into_publication(self):
        path = "model_data/ngofs2_shoreline_grid_manifest.json"
        for manifest in (None, '{"status": "partial"}', '{"status": "failed"}', 'invalid JSON'):
            with self.subTest(manifest=manifest):
                self.git("reset", "--hard", "HEAD")
                if manifest is None:
                    (self.root / path).unlink()
                else:
                    self.write(path, manifest)
                self.write("model_data/ngofs2_shoreline_grid_features.csv", "partial rows\n")
                self.write("model_data/public_archive/ngofs2_shoreline_grid_subset/partial.gz", "partial\n")
                self.write("model_data/sensing_audit.json", "completed audit\n")
                with self.assertRaises((RuntimeError, json.JSONDecodeError)):
                    validator.validate(self.root / "model_data")
                publisher.stage(self.root, outcomes(regression="success", audit="success",
                                                    ngofs2_validation="failure"), "main")
                self.assertEqual(self.staged(), {"model_data/sensing_audit.json"})

    def test_validated_outage_publishes_no_current_guidance_and_csv_deletion(self):
        name = "ngofs2_point_clear_nowcast"
        self.write(f"model_data/{name}_manifest.json", json.dumps({
            "status": "failed", "error_type": "RetrievalTimeout"}))
        validator.validate(self.root / "model_data")
        publisher.stage(self.root, outcomes(regression="success", ngofs2_validation="success"), "main")
        self.assertIn(f"model_data/{name}_normalized.csv", self.staged())
        self.assertIn("NO_CURRENT_GUIDANCE", self.git("show", f":model_data/{name}_manifest.json"))
        self.assertIn(f"D\tmodel_data/{name}_normalized.csv", self.git("diff", "--cached", "--name-status"))

    def test_successful_ngofs2_and_independent_sources_keep_existing_allowlist(self):
        self.write("model_data/public_archive/ngofs2_subset/new.gz", "new validated subset\n")
        self.write("model_data/ngofs2_point_clear_nowcast_normalized.csv", "new rows\n")
        self.write("model_data/river_forcing_normalized.csv", "artifact only\n")
        self.write("private.jpg", "private\n")
        publisher.stage(self.root, outcomes(regression="success", river="success", ngofs2_validation="success"), "main")
        self.assertEqual(self.staged(), {"model_data/public_archive/ngofs2_subset/new.gz",
                                       "model_data/ngofs2_point_clear_nowcast_normalized.csv"})

    def test_archive_budget_and_append_only_guard_remain_enforced(self):
        steps = outcomes(regression="success", river="success")
        with patch.object(publisher, "ARCHIVE_BUDGET", 1):
            with self.assertRaisesRegex(RuntimeError, "budget exceeded"):
                publisher.stage(self.root, steps, "main")
        for change in ("overwrite", "delete"):
            with self.subTest(change=change):
                self.write("model_data/public_archive/usgs/old.gz", "changed\n")
                if change == "delete":
                    (self.root / "model_data/public_archive/usgs/old.gz").unlink()
                with self.assertRaisesRegex(RuntimeError, "append-only"):
                    publisher.stage(self.root, steps, "main")
                self.assertEqual(self.staged(), set())
        self.assertEqual(publisher.ARCHIVE_BUDGET, 250_000_000)

    def test_branch_specific_outputs_stay_restricted(self):
        steps = outcomes(regression="success", weeks_bay="success", water_quality="success", main_pass="success")
        main = publisher.publication_paths(steps, "main")
        audit = publisher.publication_paths(steps, "upgrade/sensing-audit-20260906")
        self.assertIn("model_data/weeks_bay_realtime_normalized.csv", main)
        self.assertNotIn("model_data/weeks_bay_realtime_normalized.csv", audit)
        self.assertIn("model_data/water_quality_backtest.json", audit)
        self.assertNotIn("model_data/water_quality_backtest.json", main)

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_mixed_success_workflow_rebases_and_pushes_only_independent_outputs(self):
        remote = Path(self.temp.name) / "remote.git"
        self.git("clone", "--bare", str(self.root), str(remote))
        self.git("remote", "add", "origin", str(remote))
        # Move upstream ahead to exercise the actual fetch/rebase/push path.
        upstream = Path(self.temp.name) / "upstream"
        self.git("worktree", "add", "--detach", str(upstream), "HEAD")
        (upstream / "concurrent.txt").write_text("concurrent upstream update\n")
        for args in (("add", "."), ("commit", "-m", "concurrent update"), ("push", "origin", "HEAD:main")):
            subprocess.check_output(["git", *args], cwd=upstream, stderr=subprocess.STDOUT)

        independent = {"model_data/river_forcing_manifest.json", "model_data/public_archive/usgs/new.gz",
                       "model_data/weeks_bay_realtime_manifest.json", "model_data/weeks_bay_realtime_normalized.csv",
                       "model_data/public_archive/ndbc/new.gz", "model_data/sensing_audit.json",
                       "model_data/upgrade_test_report.json"}
        for path in independent:
            self.write(path, "fresh successful output\n")
        # The validator mutates earlier outage products, then fails on a later parser.
        self.write("model_data/ngofs2_point_clear_nowcast_manifest.json", json.dumps({
            "status": "failed", "error_type": "RetrievalTimeout"}))
        self.write("model_data/ngofs2_shoreline_grid_manifest.json", json.dumps({
            "status": "failed", "error_type": "ValueError", "error": "invalid parsed data"}))
        self.write("model_data/ngofs2_shoreline_grid_features.csv", "partial invalid rows\n")
        for directory in ("ngofs2_subset", "ngofs2_named_station_subset", "ngofs2_shoreline_grid_subset"):
            self.write(f"model_data/public_archive/{directory}/partial.gz", "partial subset\n")
        with self.assertRaisesRegex(RuntimeError, "parser failure"):
            validator.validate(self.root / "model_data")
        self.write("model_data/upgrade_readiness.json", "unfinished report\n")
        self.write("private.jpg", "not allowlisted\n")
        steps = outcomes(regression="success", audit="success", river="success", weeks_bay="success",
                         ngofs2_validation="failure", readiness="skipped", registry="skipped")
        script = "\n".join(line[10:] for line in PUBLISH_STEP.split("        run: |\n", 1)[1].splitlines())
        script = script.replace("python model_data/stage_sensing_outputs.py",
                                shlex.quote(Path(sys.executable).as_posix()) + " model_data/stage_sensing_outputs.py")
        runner_temp = Path(self.temp.name) / "runner"
        runner_temp.mkdir()
        env = {**os.environ, "REF_NAME": "main", "SENSING_STEPS_JSON": json.dumps(steps),
               "RUNNER_TEMP": runner_temp.as_posix()}
        result = subprocess.run([BASH, "-c", script], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.git("fetch", "origin", "main")
        self.assertEqual(set(self.git("diff", "origin/main^", "origin/main", "--name-only").splitlines()), independent)
        self.assertEqual(self.git("show", "origin/main:concurrent.txt"), "concurrent upstream update")
        self.assertEqual(self.git("show", "origin/main:model_data/ngofs2_shoreline_grid_features.csv"), "old")
        self.assertEqual(self.git("show", "origin/main:model_data/ngofs2_point_clear_nowcast_normalized.csv"), "old")
        # Excluded products remain available locally for diagnosis and later escalation.
        self.assertEqual((self.root / "model_data/river_forcing_manifest.json").read_text(), "fresh successful output\n")
        self.assertEqual((self.root / "model_data/ngofs2_shoreline_grid_features.csv").read_text(), "partial invalid rows\n")


if __name__ == "__main__":
    unittest.main()

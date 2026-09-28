"""Offline publication regressions, including a real mixed-success Git push."""
import copy
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
        for name in ("resolve_sensing_publication_conflicts.py", "reconcile_source_registry.py"):
            self.write("model_data/" + name, (ROOT / "model_data" / name).read_text())
        for path in publisher.publication_paths(outcomes(**{name: "success" for name in (
                "regression", "audit", "river", "asos", "weeks_bay", "readiness", "ngofs2_validation",
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

    def run_publication(self, steps):
        script = "\n".join(line[10:] for line in PUBLISH_STEP.split("        run: |\n", 1)[1].splitlines())
        script = script.replace("python model_data/", shlex.quote(Path(sys.executable).as_posix()) + " model_data/")
        runner_temp = Path(self.temp.name) / "runner"
        runner_temp.mkdir(exist_ok=True)
        env = {**os.environ, "REF_NAME": "main", "SENSING_STEPS_JSON": json.dumps(steps),
               "RUNNER_TEMP": runner_temp.as_posix()}
        return subprocess.run([BASH, "-c", script], cwd=self.root, env=env, capture_output=True, text=True)

    def concurrent_registry(self, *, audit=False, unexpected=False, broken=False, outage=False):
        fixture = json.loads((ROOT / "tests/fixtures/sensing_publication/concurrent_registry.json").read_text())
        path = "model_data/ongoing_source_registry_20260906.json"
        base = fixture["base_registry"]
        self.write(path, json.dumps(base, separators=(",", ":")) + "\n")
        # Historical ingestion is absent in this small production-shaped fixture.
        self.write("model_data/griidc_main_pass_20160419_manifest.json", '{"status":"not_ingested"}\n')
        self.write("model_data/current_forecast.json", '{"probability":"UNKNOWN","threshold":20,"comparator":">"}\n')
        self.git("add", ".")
        self.git("commit", "-m", "registry before concurrent research and sensing")
        remote = Path(self.temp.name) / "remote.git"
        self.git("clone", "--bare", str(self.root), str(remote))
        self.git("remote", "add", "origin", str(remote))
        upstream = Path(self.temp.name) / "upstream"
        self.git("worktree", "add", "--detach", str(upstream), "HEAD")
        research = copy.deepcopy(base)
        research["sources"] = [fixture["upstream_adcp"] if r["source_id"] == fixture["upstream_adcp"]["source_id"]
                               else r for r in research["sources"]]
        # Metadata on a refreshed source and a newly registered source must survive too.
        research["review_note"] = "Research metadata must survive sensing publication"
        research["sources"][0]["research_note"] = "Retain deployment uncertainty"
        research["sources"].append({"source_id": "research_only_new_source", "status": "UNKNOWN", "production_weight": 0})
        if broken:
            research["sources"] = [r for r in research["sources"] if r["source_id"] != "weeks_bay_nerr_swmp"]
        (upstream / path).write_text(json.dumps(research, indent=2) + "\n")
        if audit:
            (upstream / "model_data/sensing_audit.json").write_text('{"capture_id":"newer-upstream"}\n')
        if unexpected:
            (upstream / "model_data/river_forcing_manifest.json").write_text('{"status":"concurrent"}\n')
        for args in (("add", "."), ("commit", "-m", "concurrent reviewed research"), ("push", "origin", "HEAD:main")):
            subprocess.check_output(["git", *args], cwd=upstream, stderr=subprocess.STDOUT)
        self.git("fetch", "origin", "main")
        upstream_sha = self.git("rev-parse", "origin/main")

        fresh_time = "2026-09-28T15:02:00+00:00"
        river = {"status": "complete", "started_at_utc": fresh_time, "normalized_rows": 29934,
                 "raw_sha256": "a" * 64, "series": [{"station_id": "02428400", "rows": 29934,
                 "fresh": True, "parameter_code": "00060", "latest_at_utc": "2026-09-28T14:45:00+00:00"}]}
        weeks = {"status": "complete", "retrieved_at": fresh_time, "normalized_rows": 53740,
                 "sources": [{"station_id": "WKQA1", "normalized_rows": 34360, "raw_sha256": "b" * 64,
                              "latest_observed_at": "2026-09-09T16:15:00+00:00"},
                             {"station_id": "WKXA1", "normalized_rows": 19380, "raw_sha256": "c" * 64,
                              "latest_observed_at": "2026-09-28T14:45:00+00:00"}]}
        for name, doc in (("river_forcing", river), ("weeks_bay_realtime", weeks)):
            self.write(f"model_data/{name}_manifest.json", json.dumps(doc) + "\n")
        for index, name in enumerate(("ngofs2_point_clear_nowcast", "ngofs2_point_clear_forecast",
                                     "ngofs2_mobile_bay_named_stations_nowcast",
                                     "ngofs2_mobile_bay_named_stations_forecast", "ngofs2_shoreline_grid")):
            doc = {"status": "complete", "retrieved_at": fresh_time, "normalized_rows": 100 + index,
                   "station_count": 6, "raw_subset_sha256": "d" * 64, "derived_feature_rows": 20,
                   "casts": [{"selected_nodes": [{"cell": "Point Clear", "grid_y": 1, "grid_x": 2}]}]}
            if outage:
                doc = {"status": "unavailable", "current_guidance": "NO_CURRENT_GUIDANCE"}
                (self.root / f"model_data/{name}_normalized.csv").unlink()
            self.write(f"model_data/{name}_manifest.json", json.dumps(doc) + "\n")
        self.write("model_data/current_asos_weather.json", '{"precipitation_in":"UNKNOWN"}\n')
        self.write("model_data/public_archive/usgs/new.gz", "synthetic append-only archive\n")
        if audit:
            self.write("model_data/sensing_audit.json", '{"capture_id":"older-local"}\n')
        subprocess.check_output([sys.executable, "model_data/reconcile_source_registry.py"], cwd=self.root)
        local = json.loads((self.root / path).read_text())
        steps = outcomes(regression="success", registry="success", river="success", weeks_bay="success",
                         ngofs2_validation="success", asos="success", audit="success" if audit else "skipped")
        return path, research, local, steps, upstream_sha

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_concurrent_research_and_sensing_registry_survive_real_publish(self):
        path, research, local, steps, upstream_sha = self.concurrent_registry()
        result = self.run_publication(steps)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CONFLICT", result.stdout)
        self.git("fetch", "origin", "main")
        self.assertEqual(self.git("rev-parse", "origin/main^"), upstream_sha)
        merged = json.loads(self.git("show", "origin/main:" + path))
        actual = {r["source_id"]: r for r in merged["sources"]}
        expected = {r["source_id"]: r for r in local["sources"]}
        for row in research["sources"]:
            sid = row["source_id"]
            if sid.startswith("griidc_") or sid == "research_only_new_source":
                self.assertEqual(actual[sid], row)
            else:
                # Every current sensing field must equal the newly reconciled run;
                # additional upstream metadata must survive on those same rows.
                self.assertEqual(actual[sid], {**row, **expected[sid]})
            if sid.startswith("griidc_"):
                self.assertTrue(actual[sid]["production_eligibility"].startswith("ZERO_WEIGHT;"))
            else:
                self.assertEqual(actual[sid]["production_weight"], 0)
        self.assertEqual(merged["review_note"], research["review_note"])
        self.assertEqual(merged["source_interpretation_guardrails"], research["source_interpretation_guardrails"])
        self.assertEqual(actual["weeks_bay_nerr_swmp"]["realtime_normalized_rows"], 53740)
        self.assertEqual(actual["usgs_02428400_claiborne"]["normalized_rows"], 29934)
        self.assertTrue(all(v == "complete" for v in actual["noaa_ngofs2_mobile_bay"]["current_run_availability"].values()))
        self.assertEqual(actual["noaa_ngofs2_mobile_bay"]["observation_status"], "MODEL")
        self.assertEqual(self.git("show", "origin/main:model_data/current_asos_weather.json"), '{"precipitation_in":"UNKNOWN"}')
        self.assertEqual(self.git("show", "origin/main:model_data/public_archive/usgs/new.gz"), "synthetic append-only archive")
        self.assertEqual(self.git("diff", upstream_sha, "origin/main", "--", "model_data/current_forecast.json"), "")

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_combined_audit_registry_conflict_keeps_upstream_audit_and_unknown(self):
        path, research, local, steps, _ = self.concurrent_registry(audit=True, outage=True)
        result = self.run_publication(steps)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.git("fetch", "origin", "main")
        merged = json.loads(self.git("show", "origin/main:" + path))
        ngofs = next(r for r in merged["sources"] if r["source_id"] == "noaa_ngofs2_mobile_bay")
        self.assertEqual(ngofs["current_guidance"], "UNKNOWN")
        self.assertEqual(ngofs["production_weight"], 0)
        self.assertNotIn("named_station_nowcast_rows", ngofs)
        self.assertNotIn("shoreline_grid_source_hash", ngofs)
        self.assertNotIn("model_data/ngofs2_point_clear_nowcast_normalized.csv",
                         self.git("ls-tree", "-r", "--name-only", "origin/main").splitlines())
        self.assertEqual(self.git("show", "origin/main:model_data/sensing_audit.json"), '{"capture_id":"newer-upstream"}')
        self.assertEqual(next(r for r in merged["sources"] if r["source_id"].startswith("griidc_")),
                         next(r for r in research["sources"] if r["source_id"].startswith("griidc_")))

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_unexpected_conflict_blocks_registry_recovery_and_push(self):
        _, _, _, steps, upstream_sha = self.concurrent_registry(unexpected=True)
        result = self.run_publication(steps)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected or ungated publish conflict", result.stderr)
        self.git("fetch", "origin", "main")
        self.assertEqual(self.git("rev-parse", "origin/main"), upstream_sha)

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_reconciliation_failure_aborts_without_publishing(self):
        _, _, _, steps, upstream_sha = self.concurrent_registry(broken=True)
        result = self.run_publication(steps)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Canonical source registry missing weeks_bay_nerr_swmp", result.stderr)
        self.git("fetch", "origin", "main")
        self.assertEqual(self.git("rev-parse", "origin/main"), upstream_sha)

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_failed_registry_producer_cannot_publish_or_reconcile(self):
        path, research, _, steps, _ = self.concurrent_registry()
        steps["registry"] = {"outcome": "failure", "conclusion": "success"}
        result = self.run_publication(steps)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.git("fetch", "origin", "main")
        self.assertEqual(json.loads(self.git("show", "origin/main:" + path)), research)
        self.assertNotIn("Resolved sensing publication conflicts", result.stdout)

    @unittest.skipUnless(BASH, "workflow publication requires bash")
    def test_audit_only_conflict_preserves_existing_upstream_behavior(self):
        path, research, _, steps, _ = self.concurrent_registry(audit=True)
        steps["registry"] = {"outcome": "skipped"}
        result = self.run_publication(steps)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Resolved sensing publication conflicts", result.stdout)
        self.git("fetch", "origin", "main")
        self.assertEqual(self.git("show", "origin/main:model_data/sensing_audit.json"), '{"capture_id":"newer-upstream"}')
        self.assertEqual(json.loads(self.git("show", "origin/main:" + path)), research)

    def test_workflow_uses_outcomes_after_failure_without_masking_validation(self):
        self.assertIn("if: ${{ !cancelled() && steps.regression.outcome == 'success' }}", PUBLISH_STEP)
        self.assertIn("SENSING_STEPS_JSON: ${{ toJSON(steps) }}", PUBLISH_STEP)
        gate = WORKFLOW.split("      - name: Allow upstream NGOFS2 outages but reject parser failures\n")[1].split("      - name:")[0]
        self.assertIn("id: ngofs2_validation", gate)
        self.assertNotIn("continue-on-error", gate)
        # Every producer referenced by the allowlist is wired to a workflow ID.
        for name in ("regression", "audit", "river", "asos", "weeks_bay", "readiness", "ngofs2_validation",
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

    def test_asos_failure_skipped_or_missing_cannot_publish(self):
        for result in ("failure", "skipped", None):
            with self.subTest(result=result):
                for name in ("asos_weather_manifest.json", "asos_weather_normalized.json", "current_asos_weather.json"):
                    self.write("model_data/" + name, "failed producer output\n")
                self.write("model_data/public_archive/asos/partial.gz", "partial\n")
                steps = outcomes(regression="success")
                if result:
                    steps["asos"] = {"outcome": result, "conclusion": "success"}
                publisher.stage(self.root, steps, "main")
                self.assertEqual(self.staged(), set())

    def test_asos_accepted_outage_can_publish_unknown_independently(self):
        expected = {"model_data/asos_weather_manifest.json", "model_data/asos_weather_normalized.json",
                    "model_data/current_asos_weather.json"}
        self.write("model_data/asos_weather_manifest.json", '{"status":"unavailable"}\n')
        self.write("model_data/asos_weather_normalized.json", '[]\n')
        self.write("model_data/current_asos_weather.json", '{"status":"UNKNOWN"}\n')
        publisher.stage(self.root, outcomes(regression="success", asos="success",
                                            weeks_bay="failure", ngofs2_validation="failure"), "main")
        self.assertEqual(self.staged(), expected)

    def test_asos_archives_obey_append_only_guard(self):
        self.write("model_data/public_archive/asos/old.gz", "changed\n")
        with self.assertRaisesRegex(RuntimeError, "append-only"):
            publisher.stage(self.root, outcomes(regression="success", asos="success"), "main")
        self.assertEqual(self.staged(), set())

    def test_hourly_workflow_uses_producer_gate_and_clean_worktree(self):
        hourly = (ROOT / ".github/workflows/asos_weather.yml").read_text()
        self.assertIn("id: regression", hourly)
        self.assertIn("if: ${{ !cancelled() && steps.regression.outcome == 'success' }}", hourly)
        self.assertIn("SENSING_STEPS_JSON: ${{ toJSON(steps) }}", hourly)
        self.assertIn("python model_data/stage_sensing_outputs.py", hourly)
        self.assertIn('git worktree add --detach "$publish_dir" HEAD', hourly)
        self.assertNotIn("git add", hourly)
        self.assertIn("steps.asos.outcome == 'failure'", hourly)

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
        for failure in ({"error_type": "RetrievalTimeout"},
                        {"error_type": "RuntimeError", "error": "NetCDF: DAP server error"}):
            with self.subTest(failure=failure):
                self.git("reset", "--hard", "HEAD")
                self.write(f"model_data/{name}_manifest.json", json.dumps({"status": "failed", **failure}))
                validator.validate(self.root / "model_data")
                publisher.stage(self.root, outcomes(regression="success", ngofs2_validation="success"), "main")
                self.assertIn(f"model_data/{name}_normalized.csv", self.staged())
                self.assertIn("NO_CURRENT_GUIDANCE", self.git("show", f":model_data/{name}_manifest.json"))
                self.assertIn("NO_CURRENT_GUIDANCE", self.git("show", ":model_data/ngofs2_point_clear_manifest.json"))
                self.assertEqual(json.loads(self.git("show", ":model_data/ngofs2_availability.json"))[name],
                                 "unavailable")
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
                       "model_data/asos_weather_manifest.json", "model_data/asos_weather_normalized.json",
                       "model_data/current_asos_weather.json", "model_data/public_archive/asos/new.gz",
                       "model_data/weeks_bay_realtime_manifest.json", "model_data/weeks_bay_realtime_normalized.csv",
                       "model_data/public_archive/ndbc/new.gz", "model_data/sensing_audit.json",
                       "model_data/upgrade_test_report.json"}
        for path in independent:
            self.write(path, "fresh successful output\n")
        # The validator mutates earlier outage products, then fails on a later parser.
        self.write("model_data/ngofs2_point_clear_nowcast_manifest.json", json.dumps({
            "status": "failed", "error_type": "RuntimeError", "error": "NetCDF: DAP server error"}))
        self.write("model_data/ngofs2_shoreline_grid_manifest.json", json.dumps({
            "status": "failed", "error_type": "ValueError", "error": "invalid parsed data"}))
        self.write("model_data/ngofs2_shoreline_grid_features.csv", "partial invalid rows\n")
        for directory in ("ngofs2_subset", "ngofs2_named_station_subset", "ngofs2_shoreline_grid_subset"):
            self.write(f"model_data/public_archive/{directory}/partial.gz", "partial subset\n")
        with self.assertRaisesRegex(RuntimeError, "parser failure"):
            validator.validate(self.root / "model_data")
        self.write("model_data/upgrade_readiness.json", "unfinished report\n")
        self.write("private.jpg", "not allowlisted\n")
        steps = outcomes(regression="success", audit="success", river="success", asos="success", weeks_bay="success",
                         ngofs2_validation="failure", readiness="skipped", registry="skipped")
        result = self.run_publication(steps)
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

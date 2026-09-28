"""Fixture-only regressions: live drift must never block sensing publication."""
import copy
from datetime import timedelta
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model_data"))
spec = importlib.util.spec_from_file_location("freshness", ROOT / "model_data/check_current_state_freshness.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
T0 = guard.stamp("2026-09-28T03:00:00Z")


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Freshness fixture")
        self.git("config", "core.autocrlf", "false")
        self.write("model_data/sensor_contract.json", {"freshness_minutes": {"camera": 60, "weather": 90, "regional_proxy": 180}})
        self.cameras(T0 - timedelta(minutes=10))
        self.asos(T0 - timedelta(minutes=5), T0 - timedelta(minutes=10))
        self.river(T0 - timedelta(minutes=5), T0 - timedelta(minutes=10))
        self.weeks(T0 - timedelta(minutes=5), T0 - timedelta(minutes=10))
        for name in guard.MODEL_PRODUCTS:
            self.write("model_data/" + name + "_manifest.json", {"retrieved_at": T0.isoformat(), "status": "unavailable"})
        self.git("add", ".")
        self.git("commit", "-m", "baseline evidence")
        commit = self.git("rev-parse", "HEAD")
        provenance = {p: {"sha256": guard.digest((self.root / p).read_bytes()),
                          "git_blob": self.git("rev-parse", "HEAD:" + p)}
                      for p in self.git("ls-files").splitlines()}
        self.snapshot = {"snapshot_time_ct": T0.isoformat(),
                         "reconciliation": {"input_commit_sha": commit, "source_provenance": provenance},
                         "known_unknowns": ["bottom oxygen UNKNOWN", "blank precipitation UNKNOWN"],
                         "outlook": [{"range_percent": "2-6", "central_percent": 4}],
                         "alert_threshold_percent": 20, "alert_comparator": ">", "production_weight": 0}
        self.write(guard.SNAPSHOT, self.snapshot)
        self.write("model_data/current_forecast.json", {"unchanged": True, "probability": 4})

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def write(self, path, data):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data if isinstance(data, bytes) else (json.dumps(data, indent=2) + "\n").encode())

    def read(self, path):
        return json.loads((self.root / path).read_bytes())

    def archive(self, path, content):
        raw = content.encode() if isinstance(content, str) else json.dumps(content).encode()
        self.write("model_data/" + path, gzip.compress(raw))
        return guard.digest(raw)

    def cameras(self, time, failures=()):
        ids = ["camera_" + str(i) for i in range(6)]
        self.write("model_data/camera_sources.json", {"cameras": [{"camera_id": i, "access": "owner_google"} for i in ids]})
        docs = [{"capture_time_ct": time.isoformat(), "cameras": {}} for _ in range(3)]
        for cid in ids:
            if cid in failures:
                for doc in docs:
                    doc["cameras"][cid] = {"ok": False, "status": "failed"}
                continue
            shots = [{"shot": i+1, "timestamp_ct": (time + timedelta(seconds=10*i)).isoformat(),
                      "file": cid + f"_{i+1}.jpg", "bytes": 5} for i in range(3)]
            docs[0]["cameras"][cid] = {"ok": True, "timestamp_ct": shots[-1]["timestamp_ct"], "bytes": 5}
            docs[1]["cameras"][cid] = {"ok": True, "shots": shots}
            docs[2]["cameras"][cid] = {"status": "ok", "burst_shots": shots, "detectability": "low", "biology": "UNKNOWN"}
            self.write(cid + ".jpg", b"image")
        for p, d in zip(("status.json", "burst_status.json", "vision.json"), docs):
            self.write(p, d)

    def asos(self, available, observed, value=3):
        rows = [{"sensor_id": "KBFM", "parameter": "wind_speed", "value_status": "KNOWN",
                 "qc_flag": "LOCAL_CHECKS_PASS", "value": value, "unit": "kt", "production_weight": 0,
                 "available_at": available.isoformat(), "ingested_at": available.isoformat(),
                 "observed_at_utc": observed.isoformat()}]
        self.write("model_data/asos_weather_normalized.json", rows)
        self.write("model_data/asos_weather_manifest.json", {"retrieved_at_utc": available.isoformat(),
                   "status": "complete", "normalized_rows": len(rows),
                   "normalized_sha256": guard.digest((self.root / "model_data/asos_weather_normalized.json").read_bytes())})

    def river(self, available, observed, value=4000):
        raw = {"value": {"timeSeries": [{"sourceInfo": {"siteCode": [{"value": "02428400"}]},
                    "name": "USGS:02428400:00060", "variable": {"variableCode": [{"value": "00060"}],
                    "unit": {"unitCode": "ft3/s"}}, "values": [{"method": [{"methodID": 2974}],
                    "value": [{"dateTime": observed.isoformat(), "value": value, "qualifiers": ["P"]}]}]}]}}
        sha = self.archive("public_archive/usgs/test.json.gz", raw)
        self.write("model_data/river_forcing_manifest.json", {"retrieved_at_utc": available.isoformat(),
                    "status": "complete", "raw_path": "public_archive/usgs/test.json.gz", "raw_sha256": sha,
                    "source_url": "https://waterservices.usgs.gov/fixture", "normalized_rows": 1})

    def weeks(self, available, observed, value=2):
        from ingest_weeks_bay_realtime import parse_met
        import csv
        import io
        raw = "#YY MM DD hh mm WDIR WSPD\n" + observed.strftime("%Y %m %d %H %M") + f" 270 {value}\n"
        sha = self.archive("public_archive/ndbc/test.txt.gz", raw)
        rows = parse_met(raw, available)
        self.assertEqual(len(rows), 2)
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        self.write("model_data/weeks_bay_realtime_normalized.csv", out.getvalue().encode())
        self.write("model_data/weeks_bay_realtime_manifest.json", {"retrieved_at": available.isoformat(),
                   "status": "partial", "normalized_rows": 2, "sources": [
                       {"station_id": "WKXA1", "status": "complete", "raw_path": "public_archive/ndbc/test.txt.gz", "raw_sha256": sha},
                       {"station_id": "WKQA1", "status": "failed"}]})

    def report(self, *products, minutes=60):
        return guard.inspect(self.root, T0 + timedelta(minutes=minutes), products or guard.PRODUCTS)

    def model(self, name, value):
        import csv
        import io
        rows = [{"evidence_class": "MODEL", "value": value, "unit": "m/s", "production_weight": 0,
                 "model_initialized_at": (T0 - timedelta(hours=3)).isoformat(),
                 "valid_at": (T0 + timedelta(hours=3)).isoformat(),
                 "available_at": T0.isoformat(), "ingested_at": T0.isoformat()}]
        path = "public_archive/ngofs2_subset/" + name + ".json.gz"
        sha = self.archive(path, {"rows": rows})
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        normalized = name + "_normalized.csv"
        self.write("model_data/" + normalized, out.getvalue().encode())
        self.write("model_data/" + name + "_manifest.json", {
            "status": "complete", "retrieved_at": T0.isoformat(), "normalized_rows": 1,
            "normalized_csv": normalized, "subset_archive": path, "subset_sha256": sha})

    def test_each_model_recovery_and_same_time_correction(self):
        for name in guard.MODEL_PRODUCTS:
            self.model(name, 0.01)
        self.assertEqual(self.report(*guard.MODEL_PRODUCTS)["status"], "STALE")
        # Explicitly pin a reviewed model baseline, then correct values only.
        self.git("add", ".")
        self.git("commit", "-m", "reviewed model baseline")
        self.snapshot["reconciliation"]["input_commit_sha"] = self.git("rev-parse", "HEAD")
        self.snapshot["reconciliation"]["source_provenance"] = {
            p: {"sha256": guard.digest((self.root/p).read_bytes()), "git_blob": self.git("rev-parse", "HEAD:" + p)}
            for p in self.git("ls-files").splitlines()}
        self.write(guard.SNAPSHOT, self.snapshot)
        self.assertEqual(self.report(*guard.MODEL_PRODUCTS)["status"], "CURRENT")
        for name in guard.MODEL_PRODUCTS:
            self.model(name, 0.02)
        r = self.report(*guard.MODEL_PRODUCTS)
        self.assertTrue(all(x["status"] == "STALE" for x in r["sources"]))
        self.assertTrue(all(x["reason"] == "SOURCE_CONTENT_CORRECTION_OR_COVERAGE_CHANGE" for x in r["sources"]))

    def test_trace_precipitation_is_context_without_inventing_zero(self):
        rows = self.read("model_data/asos_weather_normalized.json")
        rows[0].update(parameter="precipitation_1h", value_status="TRACE", value=None)
        self.write("model_data/asos_weather_normalized.json", rows)
        m = self.read("model_data/asos_weather_manifest.json")
        m["normalized_sha256"] = guard.digest((self.root / "model_data/asos_weather_normalized.json").read_bytes())
        self.write("model_data/asos_weather_manifest.json", m)
        self.assertEqual(self.report("asos_weather")["status"], "STALE")
        self.assertIsNone(self.read("model_data/asos_weather_normalized.json")[0]["value"])

    def test_unchanged_sources_and_intentionally_unavailable_model_are_current(self):
        r = self.report()
        self.assertEqual(r["status"], "CURRENT")
        self.assertEqual(r["sources"][-1]["status"], "SOURCE_UNAVAILABLE")

    def test_newer_camera_data_fails_without_forecast_or_snapshot_change(self):
        self.cameras(T0 + timedelta(minutes=40))
        r = self.report("cameras")
        self.assertEqual(r["status"], "STALE")
        self.assertEqual(r["sources"][0]["reason"], "NEWER_SOURCE_EVIDENCE")

    def test_camera_coverage_degradation_is_material(self):
        self.cameras(T0 + timedelta(minutes=40), failures=("camera_1",))
        self.assertEqual(self.report("cameras")["status"], "STALE")

    def test_newer_environmental_products_each_fail_independently(self):
        for name, writer in (("asos_weather", self.asos), ("river_forcing", self.river), ("weeks_bay_realtime", self.weeks)):
            with self.subTest(source=name):
                writer(T0 + timedelta(minutes=40), T0 + timedelta(minutes=30))
                self.assertEqual(self.report(name)["status"], "STALE")

    def test_same_timestamp_environmental_corrections(self):
        for name, writer in (("asos_weather", self.asos), ("river_forcing", self.river), ("weeks_bay_realtime", self.weeks)):
            with self.subTest(source=name):
                writer(T0 - timedelta(minutes=5), T0 - timedelta(minutes=10), value=8)
                row = self.report(name)["sources"][0]
                self.assertEqual(row["status"], "STALE")
                self.assertEqual(row["reason"], "SOURCE_CONTENT_CORRECTION_OR_COVERAGE_CHANGE")

    def test_same_timestamp_camera_vision_and_image_corrections(self):
        for path in ("vision.json", "camera_0.jpg"):
            with self.subTest(path=path):
                self.cameras(T0 - timedelta(minutes=10))
                if path.endswith("json"):
                    doc = self.read(path)
                    doc["cameras"]["camera_0"]["biology"] = "CORRECTED_UNKNOWN"
                    self.write(path, doc)
                else:
                    self.write(path, b"other")  # Same size, different bytes.
                self.assertEqual(self.report("cameras")["status"], "STALE")

    def test_grace_boundary_and_expiry_without_new_source_push(self):
        self.asos(T0 + timedelta(minutes=10), T0 + timedelta(minutes=5))
        self.assertEqual(self.report("asos_weather", minutes=30)["status"], "PENDING_RECONCILIATION")
        self.assertEqual(self.report("asos_weather", minutes=30.01)["status"], "STALE")

    def test_refreshed_changed_source_cannot_reset_grace(self):
        self.asos(T0 + timedelta(minutes=59), T0 + timedelta(minutes=5))
        self.assertEqual(self.report("asos_weather")["status"], "STALE")

    def test_unchanged_retrieval_refresh_and_formatting_do_not_fail(self):
        for name, writer in (("asos_weather", self.asos), ("river_forcing", self.river), ("weeks_bay_realtime", self.weeks)):
            with self.subTest(source=name):
                writer(T0 + timedelta(minutes=20), T0 - timedelta(minutes=10))
                self.assertEqual(self.report(name)["status"], "CURRENT")
        self.write("status.json", json.dumps(self.read("status.json"), separators=(",", ":")).encode())
        self.assertEqual(self.report("cameras")["status"], "CURRENT")

    def test_expired_unconsumed_evidence_does_not_clear_failure(self):
        self.asos(T0 + timedelta(minutes=40), T0 + timedelta(minutes=30))
        self.assertEqual(self.report("asos_weather", minutes=300)["status"], "STALE")

    def test_already_stale_observations_not_admitted_by_recent_retrieval(self):
        self.asos(T0 + timedelta(minutes=40), T0 - timedelta(hours=4))
        row = self.report("asos_weather")["sources"][0]
        self.assertEqual(row["status"], "SOURCE_UNAVAILABLE")

    def test_declared_outage_needs_no_normalized_file(self):
        self.write("model_data/asos_weather_manifest.json", {"retrieved_at_utc": T0.isoformat(), "status": "unavailable"})
        (self.root / "model_data/asos_weather_normalized.json").unlink()
        self.assertEqual(self.report("asos_weather")["sources"][0]["status"], "SOURCE_UNAVAILABLE")

    def test_failed_producer_is_error_not_admissible_evidence(self):
        m = self.read("model_data/asos_weather_manifest.json")
        m["status"] = "failed"
        self.write("model_data/asos_weather_manifest.json", m)
        self.assertEqual(self.report("asos_weather")["status"], "ERROR")

    def test_bad_manifest_pair_and_bad_raw_archive_fail_visibly(self):
        self.write("model_data/asos_weather_normalized.json", [])
        self.assertEqual(self.report("asos_weather")["status"], "ERROR")
        self.write("model_data/public_archive/usgs/test.json.gz", gzip.compress(b"{}"))
        self.assertEqual(self.report("river_forcing")["status"], "ERROR")

    def test_missing_provenance_object_and_mismatched_digest_fail(self):
        self.asos(T0 + timedelta(minutes=40), T0 + timedelta(minutes=30))
        for field, value in (("git_blob", "0" * 40), ("sha256", "0" * 64)):
            s = copy.deepcopy(self.snapshot)
            s["reconciliation"]["source_provenance"]["model_data/asos_weather_normalized.json"][field] = value
            self.write(guard.SNAPSHOT, s)
            self.assertEqual(self.report("asos_weather")["status"], "ERROR")

    def test_blob_sha_alias_and_commit_fallback(self):
        for p in list(self.snapshot["reconciliation"]["source_provenance"]):
            item = self.snapshot["reconciliation"]["source_provenance"][p]
            item["blob_sha"] = item.pop("git_blob")
        self.snapshot["reconciliation"]["source_provenance"].pop("model_data/asos_weather_normalized.json")
        self.write(guard.SNAPSHOT, self.snapshot)
        self.asos(T0 + timedelta(minutes=40), T0 + timedelta(minutes=30))
        self.assertEqual(self.report("asos_weather")["status"], "STALE")

    def test_mixed_cycle_and_shot_identity_are_rejected(self):
        v = self.read("vision.json")
        v["cameras"]["camera_0"]["burst_shots"][0]["file"] = "other.jpg"
        self.write("vision.json", v)
        self.assertEqual(self.report("cameras")["status"], "ERROR")
        v["capture_time_ct"] = T0.isoformat()
        self.write("vision.json", v)
        self.assertEqual(self.report("cameras")["status"], "ERROR")

    def test_future_and_naive_source_times_fail(self):
        for time in ((T0 + timedelta(days=1)).isoformat(), "2026-09-28T03:00:00"):
            m = self.read("model_data/asos_weather_manifest.json")
            m["retrieved_at_utc"] = time
            self.write("model_data/asos_weather_manifest.json", m)
            self.assertEqual(self.report("asos_weather")["status"], "ERROR")


    def test_mixed_weeks_snapshot_provenance_is_rejected(self):
        baseline = (self.root / "model_data/weeks_bay_realtime_normalized.csv").read_bytes()
        lines = baseline.splitlines(keepends=True)
        self.assertGreaterEqual(len(lines), 2)
        mixed = baseline + lines[-1]
        self.write("model_data/weeks_bay_realtime_normalized.csv", mixed)
        self.git("add", "model_data/weeks_bay_realtime_normalized.csv")
        self.git("commit", "-m", "foreign Weeks CSV generation")
        foreign_blob = self.git("rev-parse", "HEAD:model_data/weeks_bay_realtime_normalized.csv")
        self.write("model_data/weeks_bay_realtime_normalized.csv", baseline)
        s = copy.deepcopy(self.snapshot)
        s["reconciliation"]["source_provenance"]["model_data/weeks_bay_realtime_normalized.csv"] = {
            "sha256": guard.digest(mixed), "git_blob": foreign_blob}
        self.write(guard.SNAPSHOT, s)
        row = self.report("weeks_bay_realtime")["sources"][0]
        self.assertEqual(row["status"], "ERROR")
        self.assertEqual(row["reason"], "Weeks Bay row count mismatch")

    def test_cli_is_read_only_and_nonzero_for_stale(self):
        self.asos(T0 + timedelta(minutes=40), T0 + timedelta(minutes=30))
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        r = subprocess.run([sys.executable, "-B", str(ROOT / "model_data/check_current_state_freshness.py"),
                            "--root", str(self.root), "--as-of", (T0 + timedelta(minutes=60)).isoformat()], capture_output=True)
        self.assertEqual(r.returncode, 1, r.stderr.decode())
        self.assertEqual(json.loads(r.stdout)["status"], "STALE")
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class ProductionWeeksBayArchiveTests(unittest.TestCase):
    def _station_counts(self, reader, manifest):
        from ingest_weeks_bay_realtime import parse_met, parse_ocean
        available = guard.stamp(manifest["retrieved_at"])
        actual, expected = {}, {}
        for source in manifest["sources"]:
            if source["status"] != "complete":
                continue
            parser = {"WKXA1": parse_met, "WKQA1": parse_ocean}[source["station_id"]]
            raw = reader.archive(source["raw_path"], source["raw_sha256"])
            actual[source["station_id"]] = len(parser(raw.decode("utf-8"), available))
            expected[source["station_id"]] = source["normalized_rows"]
        return actual, expected

    def test_current_archives_reparse_to_published_station_counts(self):
        reader = guard.Reader(ROOT)
        manifest = reader.json("model_data/weeks_bay_realtime_manifest.json")
        self.assertEqual(*self._station_counts(reader, manifest))



class WorkflowTests(unittest.TestCase):
    def test_independent_workflow_observes_token_pushes_and_grace_expiry(self):
        workflow = (ROOT / ".github/workflows/current_state_freshness.yml").read_text()
        self.assertIn("contents: read", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("cron: '17,47 * * * *'", workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)
        for name in ("sensing_quality", "asos_weather"):
            producer = (ROOT / f".github/workflows/{name}.yml").read_text()
            self.assertIn(producer.splitlines()[0].removeprefix("name: "), workflow)
            self.assertNotIn("check_current_state_freshness", producer)
            self.assertNotIn("current-state-status", producer)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("GITHUB_STEP_SUMMARY", workflow)
        self.assertIn("actions/upload-artifact", workflow)


if __name__ == "__main__":
    unittest.main()

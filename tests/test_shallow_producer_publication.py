"""Run the real ASOS/WQP publication shells from genuine depth-one checkouts.

All repositories and concurrent writers are disposable, local fixtures. A Git
launcher injects real upstream commits immediately before selected pushes; it
never fakes a Git result. Only the retry delay is skipped. No provider ingestion
or network remote is used, and the workflow shell itself is not rewritten.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
REAL_GIT = shutil.which("git")
SOURCES = {
    "asos": {
        "asos": ("asos_weather_manifest.json", "asos_weather_normalized.json", "current_asos_weather.json"),
        "coops": ("noaa_water_level_manifest.json", "noaa_water_level_normalized.json", "current_noaa_water_level.json"),
        "usgs": ("river_forcing_manifest.json",),
    },
    "wqp": {"wqp": ("water_quality_ingest_manifest.json", "water_quality_backtest.json", "water_quality_run_summary.json")},
}
WORKFLOWS = {"asos": "asos_weather.yml", "wqp": "water_quality_ingest.yml"}
STEP_NAMES = {
    "asos": "Publish independent weather and river evidence, including UNKNOWN on source outage",
    "wqp": "Persist compact records and immutable public raw observations",
}


def publication_shell(producer):
    workflow = (ROOT / ".github/workflows" / WORKFLOWS[producer]).read_text()
    step = workflow.split("      - name: " + STEP_NAMES[producer] + "\n", 1)[1]
    step = step.split("\n      - name:", 1)[0]
    lines = step.split("        run: |\n", 1)[1].splitlines()
    if any(line and not line.startswith("          ") for line in lines):
        raise AssertionError("Unexpected publication-shell indentation")
    return "\n".join(line[10:] if line else "" for line in lines) + "\n"


# Git operations still execute the real binary against local file:// remotes.
# In race tests, an independent full clone advances main before the publisher's
# push, making the real push fail non-fast-forward and exercising the real loop.
GIT_LAUNCHER = r'''import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
real = os.environ["SHALLOW_TEST_REAL_GIT"]
with open(os.environ["SHALLOW_TEST_GIT_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\n")
if args and args[0] == "push" and os.environ.get("SHALLOW_TEST_RACE"):
    state = pathlib.Path(os.environ["SHALLOW_TEST_RACE_COUNT"])
    count = int(state.read_text()) + 1 if state.exists() else 1
    state.write_text(str(count))
    if count == 1 or os.environ["SHALLOW_TEST_RACE"] == "every":
        actor = pathlib.Path(os.environ["SHALLOW_TEST_ACTOR"])
        path = actor / ("concurrent-race-%s.txt" % count)
        path.write_text("independent upstream update %s\n" % count)
        for command in (("add", path.name), ("commit", "-m", "concurrent push race %s" % count),
                        ("push", "origin", "HEAD:main")):
            subprocess.run([real, *command], cwd=actor, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
sys.exit(subprocess.run([real, *args]).returncode)
'''


class LocalProducer:
    def __init__(self, case, producer, *, capacity_limits=None):
        self.case = case
        self.producer = producer
        temp = tempfile.TemporaryDirectory(prefix="shallow-publication-")
        case.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.seed = self.base / "seed"
        self.remote = self.base / "remote.git"
        self.root = self.base / "runner"
        self.actor = self.base / "concurrent-writer"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.seed.mkdir()
        self.runner_temp = self.base / "runner-temp"
        self.runner_temp.mkdir()
        self.log = self.base / "git-commands.jsonl"
        self.env = dict(os.environ)
        # Do not inherit a caller's repository, credentials, Git hooks, or network
        # configuration. File transport is the only protocol these fixtures allow.
        for key in list(self.env):
            if key.startswith("GIT_"):
                self.env.pop(key)
        self.env.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Publication fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Publication fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "REF_NAME": "main", "RUNNER_TEMP": self.runner_temp.as_posix(),
            "GITHUB_STEP_SUMMARY": (self.base / "summary.md").as_posix(),
            "SHALLOW_TEST_REAL_GIT": str(REAL_GIT),
            "SHALLOW_TEST_GIT_LOG": str(self.log),
            "SHALLOW_TEST_RACE_COUNT": str(self.base / "push-count"),
            "SHALLOW_TEST_ACTOR": str(self.actor),
        })
        self.git(self.seed, "init", "-b", "main")
        self.git(self.seed, "config", "core.autocrlf", "false")
        for name in ("stage_sensing_outputs.py", "data_retention_policy.json"):
            self.write(self.seed, "model_data/" + name, (ROOT / "model_data" / name).read_bytes())
        if capacity_limits is not None:
            policy_path = self.seed / "model_data/data_retention_policy.json"
            policy = json.loads(policy_path.read_text())
            public = next(row for row in policy["storage_classes"]
                          if row["class"] == "raw_public_environmental_observation")
            soft, hard = capacity_limits
            public.update(public_git_soft_budget_bytes=soft, public_git_hard_budget_bytes=hard)
            policy_path.write_text(json.dumps(policy) + "\n")
        self.old_archives = {}
        self.new_archives = {}
        self.outputs = set()
        for source, names in SOURCES[producer].items():
            raw = ("historic %s observation\n" % source).encode()
            path, compressed = self.archive(source, raw)
            self.old_archives[path] = compressed
            self.write(self.seed, path, compressed)
            for name in names:
                path = "model_data/" + name
                self.outputs.add(path)
                self.write(self.seed, path, b'{"fixture":"baseline"}\n')
        self.commit(self.seed, "historical archives and publication helper")
        self.historical = self.git(self.seed, "rev-parse", "HEAD").strip().decode()
        # The archive predates the boundary. A one-commit repository would not
        # establish whether --depth=1 genuinely excludes its earlier history.
        for number in (1, 2):
            self.write(self.seed, "history-%s.txt" % number, b"older independent commit\n")
            self.commit(self.seed, "unrelated historical commit %s" % number)
        self.git(self.seed, "clone", "--bare", str(self.seed), str(self.remote))
        url = self.remote.as_uri()
        self.git(self.seed, "clone", "--depth", "1", "--branch", "main", url, str(self.root))
        self.git(self.seed, "clone", "--branch", "main", url, str(self.actor))
        self.baseline = self.remote_head()
        case.assertEqual(self.git(self.root, "rev-parse", "--is-shallow-repository"), b"true\n")
        case.assertEqual(self.git(self.root, "rev-list", "--count", "HEAD"), b"1\n")
        case.assertEqual(self.git(self.remote, "rev-list", "--count", "main"), b"3\n")
        case.assertEqual((self.root / ".git/shallow").read_text().strip(), self.baseline)
        missing = subprocess.run([REAL_GIT, "cat-file", "-e", self.historical + "^{commit}"],
                                 cwd=self.root, env=self.env, capture_output=True)
        case.assertNotEqual(missing.returncode, 0, "Historical commit must be outside the shallow clone")
        self.make_launchers()

    @staticmethod
    def write(root, path, content):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    @staticmethod
    def archive(source, raw):
        digest = hashlib.sha256(raw).hexdigest()
        return "model_data/public_archive/%s/%s.csv.gz" % (source, digest), gzip.compress(raw, mtime=0)

    def git(self, root, *args):
        return subprocess.check_output([REAL_GIT, *args], cwd=root, env=self.env, stderr=subprocess.STDOUT)

    def commit(self, root, message):
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", message)
        return self.git(root, "rev-parse", "HEAD").strip().decode()

    def remote_head(self):
        return self.git(self.remote, "rev-parse", "main").strip().decode()

    def remote_bytes(self, path):
        return self.git(self.remote, "show", "main:" + path)

    def remote_paths(self):
        return set(self.git(self.remote, "ls-tree", "-r", "--name-only", "main").decode().splitlines())

    def make_launchers(self):
        launcher = self.base / "git-launcher.py"
        launcher.write_text(GIT_LAUNCHER)
        python = shlex.quote(Path(sys.executable).as_posix())
        wrappers = {
            "python": "exec " + python + ' "$@"\n',
            "git": "exec " + python + " " + shlex.quote(launcher.as_posix()) + ' "$@"\n',
            # Remove only wall-clock delay, leaving the exact retry shell intact.
            "sleep": 'printf "%s\\n" "$*" >> "$SHALLOW_TEST_SLEEP_LOG"\n',
        }
        for name, body in wrappers.items():
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + body)
            path.chmod(0o755)
        self.env["PATH"] = str(self.bin) + os.pathsep + os.environ.get("PATH", "")
        self.env["SHALLOW_TEST_SLEEP_LOG"] = str(self.base / "sleep.log")

    def prepare_outputs(self):
        for source, names in SOURCES[self.producer].items():
            raw = ("new %s observation from this run\n" % source).encode()
            path, compressed = self.archive(source, raw)
            self.new_archives[path] = compressed
            self.write(self.root, path, compressed)
            content = (json.dumps({"fixture": "local run", "raw_path": path,
                                   "raw_sha256": hashlib.sha256(raw).hexdigest()}) + "\n").encode()
            for name in names:
                self.write(self.root, "model_data/" + name, content)
        self.write(self.root, "private-unrelated.txt", b"not allowlisted\n")
        artifact = "river_forcing_normalized.csv" if self.producer == "asos" else "water_quality_normalized.csv"
        self.write(self.root, "model_data/" + artifact, b"artifact only\n")
        return self.outputs | self.new_archives.keys()

    def advance(self, files):
        for path, content in files.items():
            self.write(self.actor, path, content)
        sha = self.commit(self.actor, "independent concurrent main update")
        self.git(self.actor, "push", "origin", "HEAD:main")
        return sha

    def run(self, *, race=None, steps=None):
        env = dict(self.env)
        env["SENSING_STEPS_JSON"] = json.dumps(steps if steps is not None else {
            name: {"outcome": "success"} for name in ("regression", "asos", "noaa_water_level", "river")
        })
        if race:
            env["SHALLOW_TEST_RACE"] = race
        return subprocess.run([BASH, "-c", publication_shell(self.producer)], cwd=self.root,
                              env=env, capture_output=True, text=True, timeout=60)

    def commands(self, command):
        if not self.log.exists():
            return []
        return [row for row in map(json.loads, self.log.read_text().splitlines())
                if row["args"][0] == command]

    def assert_archives_retained(self):
        for path, content in self.old_archives.items():
            self.case.assertEqual(self.remote_bytes(path), content)
            self.case.assertEqual(hashlib.sha256(gzip.decompress(self.remote_bytes(path))).hexdigest(),
                                  Path(path).name.split(".")[0])
        self.case.assertEqual(self.git(self.root, "rev-parse", "--is-shallow-repository"), b"true\n")

    def assert_published(self, parent, expected):
        self.case.assertEqual(self.git(self.remote, "rev-parse", "main^").strip().decode(), parent)
        changed = set(self.git(self.remote, "diff", "--name-only", "main^", "main").decode().splitlines())
        self.case.assertEqual(changed, set(expected))
        for path, content in self.new_archives.items():
            if path in expected:
                self.case.assertEqual(self.remote_bytes(path), content)
                self.case.assertEqual(hashlib.sha256(gzip.decompress(content)).hexdigest(), Path(path).name.split(".")[0])
        self.case.assertNotIn("private-unrelated.txt", self.remote_paths())
        self.assert_archives_retained()


@unittest.skipUnless(BASH and REAL_GIT, "requires bash and git")
class ShallowProducerPublicationTests(unittest.TestCase):
    def test_history_dependent_current_state_jobs_keep_full_history(self):
        workflow = (ROOT / ".github/workflows/current_state_freshness.yml").read_text()
        for job in ("reconcile", "current-state-status"):
            with self.subTest(job=job):
                body = workflow.split("\n  " + job + ":\n", 1)[1]
                checkout = body.split("      - uses: actions/checkout@v5\n", 1)[1].split("      - ", 1)[0]
                self.assertIn("ref: main\n", checkout)
                self.assertIn("fetch-depth: 0\n", checkout)
                self.assertNotIn("${{", checkout)

    def test_main_shallow_checkout_keeps_non_main_full_history(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                workflow = (ROOT / ".github/workflows" / WORKFLOWS[producer]).read_text()
                checkout = workflow.split("      - uses: actions/checkout@v4\n", 1)[1].split("      - ", 1)[0]
                self.assertIn("fetch-depth: ${{ github.ref == 'refs/heads/main' && 1 || 0 }}", checkout)
                if producer == "asos":
                    self.assertIn("ref: ${{ github.ref_name }}", checkout)
                shell = publication_shell(producer)
                self.assertNotIn("--unshallow", shell)
                self.assertNotIn("--force", shell)

    def test_normal_publication_preserves_allowlist_and_historical_hashes(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                fixture = LocalProducer(self, producer)
                expected = fixture.prepare_outputs()
                result = fixture.run()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                fixture.assert_published(fixture.baseline, expected)
                self.assertEqual(len(fixture.commands("push")), 1)

    def test_concurrent_unrelated_main_advance_is_retained(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                fixture = LocalProducer(self, producer)
                expected = fixture.prepare_outputs()
                upstream = fixture.advance({"concurrent.txt": b"upstream must survive\n"})
                result = fixture.run()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                fixture.assert_published(upstream, expected)
                self.assertEqual(fixture.remote_bytes("concurrent.txt"), b"upstream must survive\n")

    def test_real_push_race_rebases_and_retries_successfully(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                fixture = LocalProducer(self, producer)
                expected = fixture.prepare_outputs()
                result = fixture.run(race="first")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("[rejected]", result.stderr)
                self.assertEqual(len(fixture.commands("push")), 2)
                self.assertEqual((fixture.base / "sleep.log").read_text(), "3\n")
                upstream = fixture.git(fixture.actor, "rev-parse", "HEAD").strip().decode()
                fixture.assert_published(upstream, expected)
                self.assertEqual(fixture.remote_bytes("concurrent-race-1.txt"), b"independent upstream update 1\n")

    def test_repeated_real_push_races_exhaust_three_attempts_without_publication(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                fixture = LocalProducer(self, producer)
                fixture.prepare_outputs()
                result = fixture.run(race="every")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(fixture.commands("push")), 3)
                self.assertEqual(result.stderr.count("[rejected]"), 3)
                self.assertEqual((fixture.base / "sleep.log").read_text(), "3\n3\n3\n")
                self.assertEqual(fixture.remote_head(), fixture.git(fixture.actor, "rev-parse", "HEAD").strip().decode())
                self.assertTrue(fixture.new_archives.keys().isdisjoint(fixture.remote_paths()))
                for path in fixture.outputs:
                    self.assertEqual(fixture.remote_bytes(path), b'{"fixture":"baseline"}\n')
                fixture.assert_archives_retained()

    def test_overlapping_output_or_new_archive_conflicts_fail_closed(self):
        for producer in SOURCES:
            for conflict in ("output", "archive"):
                with self.subTest(producer=producer, conflict=conflict):
                    fixture = LocalProducer(self, producer)
                    fixture.prepare_outputs()
                    if conflict == "output":
                        path = sorted(fixture.outputs)[0]
                        upstream_bytes = b'{"fixture":"upstream conflict"}\n'
                    else:
                        path = next(iter(fixture.new_archives))
                        upstream_bytes = gzip.compress(b"different upstream bytes at the same new path", mtime=0)
                    upstream = fixture.advance({path: upstream_bytes})
                    result = fixture.run()
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("CONFLICT", result.stdout + result.stderr)
                    self.assertEqual(fixture.remote_head(), upstream)
                    self.assertEqual(fixture.remote_bytes(path), upstream_bytes)
                    self.assertEqual(fixture.commands("push"), [])
                    for new_path in fixture.new_archives:
                        if new_path != path:
                            self.assertNotIn(new_path, fixture.remote_paths())
                    fixture.assert_archives_retained()
                    if producer == "asos":
                        # The detached publication worktree must abort its rebase.
                        self.assertEqual(len(fixture.commands("rebase")), 2)
                        self.assertEqual(fixture.commands("rebase")[-1]["args"], ["rebase", "--abort"])

    def test_archive_mutation_and_deletion_are_rejected_before_commit(self):
        for producer, sources in SOURCES.items():
            for source in sources:
                for change in ("mutate", "delete"):
                    with self.subTest(producer=producer, source=source, change=change):
                        fixture = LocalProducer(self, producer)
                        fixture.prepare_outputs()
                        path = next(path for path in fixture.old_archives if "/%s/" % source in path)
                        if change == "mutate":
                            fixture.write(fixture.root, path, b"changed historical archive")
                        else:
                            (fixture.root / path).unlink()
                        result = fixture.run()
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("append-only", result.stderr)
                        self.assertEqual(fixture.remote_head(), fixture.baseline)
                        self.assertEqual(fixture.git(fixture.root, "diff", "--cached", "--name-only"), b"")
                        self.assertEqual(fixture.commands("commit"), [])
                        self.assertEqual(fixture.commands("push"), [])
                        fixture.assert_archives_retained()

    def test_dirty_index_is_rejected_before_commit(self):
        for producer in SOURCES:
            with self.subTest(producer=producer):
                fixture = LocalProducer(self, producer)
                fixture.prepare_outputs()
                fixture.git(fixture.root, "add", "private-unrelated.txt")
                result = fixture.run()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("empty index", result.stderr)
                self.assertEqual(fixture.remote_head(), fixture.baseline)
                self.assertEqual(fixture.git(fixture.root, "diff", "--cached", "--name-only"), b"private-unrelated.txt\n")
                self.assertEqual(fixture.commands("commit"), [])
                self.assertEqual(fixture.commands("push"), [])
                fixture.assert_archives_retained()

    def test_asos_failed_or_season_skipped_producers_do_not_leak(self):
        fixture = LocalProducer(self, "asos")
        fixture.prepare_outputs()
        result = fixture.run(steps={
            "regression": {"outcome": "success"}, "asos": {"outcome": "success"},
            "noaa_water_level": {"outcome": "failure", "conclusion": "success"},
            "river": {"outcome": "success", "outputs": {"season_skipped": "true"}},
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = {"model_data/" + name for name in SOURCES["asos"]["asos"]}
        expected.update(path for path in fixture.new_archives if "/asos/" in path)
        fixture.assert_published(fixture.baseline, expected)
        for path in fixture.outputs - expected:
            self.assertEqual(fixture.remote_bytes(path), b'{"fixture":"baseline"}\n')
        for path in fixture.new_archives.keys() - expected:
            self.assertNotIn(path, fixture.remote_paths())

    def test_wqp_capacity_is_checked_again_after_rebase(self):
        hard = 256
        fixture = LocalProducer(self, "wqp", capacity_limits=(hard - 1, hard))
        fixture.prepare_outputs()
        old_size = sum(map(len, fixture.old_archives.values()))
        new_size = sum(map(len, fixture.new_archives.values()))
        # Scale only this disposable policy to avoid allocating a 500 MB fixture.
        # Both writers are individually below the ceiling; their merged archive
        # exceeds it. The production 250/500 MB policy is asserted unchanged below.
        policy_path = "model_data/data_retention_policy.json"
        policy = json.loads((ROOT / policy_path).read_text())
        public = next(row for row in policy["storage_classes"] if row["class"] == "raw_public_environmental_observation")
        self.assertEqual(public["public_git_soft_budget_bytes"], 250_000_000)
        self.assertEqual(public["public_git_hard_budget_bytes"], 500_000_000)
        self.assertLess(old_size + new_size, hard)
        shared_path = "model_data/public_archive/usgs/concurrent-capacity.fixture"
        extra = b"x" * (hard - old_size - 1)
        self.assertLess(old_size + len(extra), hard)
        self.assertGreater(old_size + new_size + len(extra), hard)
        upstream = fixture.advance({shared_path: extra})
        result = fixture.run()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("budget exceeded", result.stderr)
        self.assertEqual(result.stdout.count("Public archive:"), 2)
        self.assertEqual(len(fixture.commands("commit")), 1)
        self.assertEqual(len(fixture.commands("pull")), 1)
        self.assertEqual(fixture.commands("push"), [])
        self.assertEqual(fixture.git(fixture.root, "rev-parse", "HEAD^").strip().decode(), upstream)
        self.assertEqual(fixture.remote_head(), upstream)
        self.assertEqual(fixture.remote_bytes(shared_path), extra)
        self.assertTrue(fixture.new_archives.keys().isdisjoint(fixture.remote_paths()))
        for path in fixture.outputs:
            self.assertEqual(fixture.remote_bytes(path), b'{"fixture":"baseline"}\n')
        fixture.assert_archives_retained()


if __name__ == "__main__":
    unittest.main()

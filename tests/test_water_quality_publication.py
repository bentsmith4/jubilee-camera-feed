"""Execute the weekly publication shell against local Git repositories."""
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_sensing_publication import publisher, ROOT, BASH

WORKFLOW = (ROOT / '.github/workflows/water_quality_ingest.yml').read_text()

class WaterPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        for name in ('stage_sensing_outputs.py', 'data_retention_policy.json'):
            self.write('model_data/' + name, (ROOT / 'model_data' / name).read_bytes())
        self.raw = b'station,oxygen\nfixture,2.5\n'
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.archive = 'model_data/public_archive/wqp/' + self.digest + '.csv.gz'
        self.write(self.archive, gzip.compress(self.raw, mtime=0))
        for name in ('ingest_manifest', 'backtest', 'run_summary'):
            self.write('model_data/water_quality_' + name + '.json', b'{}\n')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.before = (self.root / self.archive).read_bytes()

    def write(self, path, data):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.STDOUT)

    def set_size(self, total):
        # Sparse unrelated-source fixture proves the guard measures the shared archive.
        p = self.root / 'model_data/public_archive/usgs/capacity.fixture'
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('wb') as f:
            f.truncate(total - len(self.before))

    def test_threshold_boundaries_and_october_inventory(self):
        for size, warn, blocked in ((250_000_000, False, False), (250_000_001, True, False),
                                    (252_760_278, True, False), (500_000_000, True, False),
                                    (500_000_001, False, True)):
            with self.subTest(size=size):
                self.git('reset', '--mixed', 'HEAD')
                self.set_size(size)
                output = io.StringIO()
                summary = Path(self.temp.name) / 'summary'
                with contextlib.redirect_stdout(output), patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(summary)}):
                    if blocked:
                        with self.assertRaisesRegex(RuntimeError, 'budget exceeded'):
                            publisher.stage_water_quality(self.root)
                        self.assertEqual(self.git('diff', '--cached', '--name-only'), b'')
                    else:
                        publisher.stage_water_quality(self.root)
                self.assertEqual('::warning' in output.getvalue(), warn)
                self.assertIn('remaining', summary.read_text())
                self.assertEqual((self.root / self.archive).read_bytes(), self.before)
                self.assertEqual(hashlib.sha256(gzip.decompress(self.before)).hexdigest(), self.digest)

    def test_invalid_policy_fails_closed(self):
        path = self.root / 'model_data/data_retention_policy.json'
        original = json.loads(path.read_text())
        for soft, hard in ((0, 500), (501, 500), (True, 500), (250, '500')):
            data = json.loads(json.dumps(original))
            data['storage_classes'][0].update(public_git_soft_budget_bytes=soft, public_git_hard_budget_bytes=hard)
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                publisher.stage_water_quality(self.root)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            publisher.stage_water_quality(self.root)

    def test_archive_changes_and_dirty_index_rejected(self):
        for deleted in (False, True):
            self.write(self.archive, b'changed')
            if deleted:
                (self.root / self.archive).unlink()
            with self.assertRaisesRegex(RuntimeError, 'append-only'):
                publisher.stage_water_quality(self.root)
            self.assertEqual(self.git('diff', '--cached', '--name-only'), b'')
        self.write(self.archive, self.before)
        self.write('unrelated.txt', b'private')
        self.git('add', 'unrelated.txt')
        with self.assertRaisesRegex(RuntimeError, 'empty index'):
            publisher.stage_water_quality(self.root)

    @unittest.skipUnless(BASH, 'requires bash')
    def test_actual_workflow_publishes_allowlist_with_hashes_intact(self):
        remote = Path(self.temp.name) / 'remote.git'
        self.git('clone', '--bare', str(self.root), str(remote))
        self.git('remote', 'add', 'origin', str(remote))
        self.set_size(252_760_278)
        new_raw = b'new water-quality observation'
        new_hash = hashlib.sha256(new_raw).hexdigest()
        new_path = 'model_data/public_archive/wqp/' + new_hash + '.csv.gz'
        self.write(new_path, gzip.compress(new_raw, mtime=0))
        manifest = {'raw_sha256': new_hash, 'raw_path': new_path}
        self.write('model_data/water_quality_ingest_manifest.json', json.dumps(manifest).encode())
        self.write('unrelated.txt', b'not published')
        step = WORKFLOW.split('      - name: Persist compact records and immutable public raw observations\n')[1]
        script = '\n'.join(line[10:] for line in step.split('        run: |\n')[1].splitlines())
        script = script.replace('python model_data/', shlex.quote(Path(sys.executable).as_posix()) + ' model_data/')
        result = subprocess.run([BASH, '-c', script], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('::warning', result.stdout)
        changed = set(self.git('diff', 'HEAD~1', 'HEAD', '--name-only').decode().splitlines())
        self.assertEqual(changed, {new_path, 'model_data/water_quality_ingest_manifest.json'})
        self.assertEqual(self.git('show', 'HEAD:' + self.archive), self.before)
        published = subprocess.check_output(['git', '--git-dir', str(remote), 'show', 'main:' + new_path])
        self.assertEqual(hashlib.sha256(gzip.decompress(published)).hexdigest(), new_hash)

    def test_workflow_scientific_and_schedule_gates_preserved(self):
        self.assertIn("cron: '17 11 * * 2'", WORKFLOW)
        self.assertNotIn('continue-on-error', WORKFLOW)
        self.assertLess(WORKFLOW.index('python -m unittest'), WORKFLOW.index('python model_data/ingest_water_quality.py'))
        self.assertLess(WORKFLOW.index('python model_data/backtest_water_quality.py'), WORKFLOW.index('--water-quality'))
        self.assertIn('if: always()', WORKFLOW)
        self.assertIn('retention-days: 90', WORKFLOW)
        self.assertIn('git pull --rebase origin main\n            python model_data/stage_sensing_outputs.py --check-archive', WORKFLOW)

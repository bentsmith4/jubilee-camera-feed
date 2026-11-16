"""Exercise the actual workflow program against small, offline Git histories."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = (ROOT / 'tools/check_register_append.py').read_bytes()
REGISTER = 'model_data/MODEL_WORK_REGISTER.md'
WORKFLOW = (ROOT / '.github/workflows/register_integrity.yml').read_text()
PROGRAM = textwrap.dedent(WORKFLOW.split("          python -I - <<'PYTHON'\n", 1)[1].split('          PYTHON', 1)[0])
BOOTSTRAP_BASE = '952a467f9af03c17c0210a27979cdc72112c9d7a'


class RegisterWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.env = dict(os.environ, GIT_AUTHOR_NAME='test', GIT_COMMITTER_NAME='test',
                        GIT_AUTHOR_EMAIL='test@example.invalid', GIT_COMMITTER_EMAIL='test@example.invalid')
        self.git('init', '-q')
        self.initial = self.commit(b'Old receipt\n')
        self.base = self.commit(b'Old receipt\nConcurrent main receipt\n', [self.initial])
        self.head = self.commit(b'Old receipt\nPR receipt\n', [self.initial])

    def git(self, *args, data=None):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], input=data, env=self.env)

    def commit(self, register, parents=(), checker=CHECKER):
        self.git('read-tree', '--empty')
        for path, content in [(REGISTER, register), ('tools/check_register_append.py', checker)]:
            if content is not None:
                blob = self.git('hash-object', '-w', '--stdin', data=content).decode().strip()
                self.git('update-index', '--add', '--cacheinfo', '100644', blob, path)
        tree = self.git('write-tree').decode().strip()
        args = ['commit-tree', tree]
        for parent in parents:
            args += ['-p', parent]
        return self.git(*args, data=b'fixture\n').decode().strip()

    def run_guard(self, merged, base=None, head=None, number='99', program=PROGRAM):
        self.git('update-ref', 'HEAD', merged)
        return subprocess.run([sys.executable, '-I', '-c', program], cwd=self.repo,
                              env=dict(self.env, BASE=base or self.base, PR_HEAD=head or self.head,
                                       PR_NUMBER=number), capture_output=True, text=True)

    def merge(self, register, checker=CHECKER):
        return self.commit(register, [self.base, self.head], checker)

    def test_concurrent_append_retained(self):
        result = self.run_guard(self.merge(b'Old receipt\nConcurrent main receipt\nPR receipt\n'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('trusted base', result.stdout)

    def test_concurrent_append_lost(self):
        self.assertNotEqual(self.run_guard(self.merge(b'Old receipt\nPR receipt\n')).returncode, 0)

    def test_proposed_checker_cannot_approve_loss(self):
        result = self.run_guard(self.merge(b'Old receipt\n', b'raise SystemExit(0)\n'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Historical register bytes', result.stderr)

    def test_proposed_checker_not_executed(self):
        result = self.run_guard(self.merge(b'Old receipt\nConcurrent main receipt\n', b'raise SystemExit(23)\n'))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_corrupt_candidate(self):
        for value in (None, b'Old receipt\nConcurrent main receipt\n\x00', b'Old receipt\nConcurrent main receipt\n\xff'):
            with self.subTest(value=value):
                self.assertNotEqual(self.run_guard(self.merge(value)).returncode, 0)

    def test_stale_event_base(self):
        result = self.run_guard(self.merge(b'Old receipt\nConcurrent main receipt\n'), base=self.initial)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('proposed merge', result.stderr)

    def test_missing_ref_and_wrong_head(self):
        merged = self.merge(b'Old receipt\nConcurrent main receipt\n')
        for kwargs in ({'base': 'f' * 40}, {'head': self.initial}, {'base': '--help'}):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(self.run_guard(merged, **kwargs).returncode, 0)

    def test_missing_base_register(self):
        base = self.commit(None, [self.initial])
        merged = self.commit(b'PR receipt\n', [base, self.head])
        self.assertNotEqual(self.run_guard(merged, base=base).returncode, 0)

    def test_absent_base_checker_requires_pinned_install(self):
        base = self.commit(b'Old receipt\n', [self.initial], checker=None)
        merged = self.commit(b'Old receipt\nPR receipt\n', [base, self.head])
        self.assertNotEqual(self.run_guard(merged, base=base, number='160').returncode, 0)
        # Substitute only the reviewed installation SHA with the synthetic fixture SHA.
        program = PROGRAM.replace(BOOTSTRAP_BASE, base)
        result = self.run_guard(merged, base=base, number='160', program=program)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('pinned first-install', result.stdout)
        self.assertNotEqual(self.run_guard(merged, base=base, number='99', program=program).returncode, 0)
        malicious = self.commit(b'Old receipt\nPR receipt\n', [base, self.head], b'raise SystemExit(0)\n')
        self.assertNotEqual(self.run_guard(malicious, base=base, number='160', program=program).returncode, 0)

    def test_workflow_contract(self):
        # Configuration regression, not a claim of tamper-proof hosting.
        self.assertIn('fetch-depth: 2', WORKFLOW)
        self.assertIn('contents: read', WORKFLOW)
        self.assertIn('persist-credentials: false', WORKFLOW)
        self.assertNotIn('pull_request_target:', WORKFLOW)
        self.assertNotIn('paths:', WORKFLOW)

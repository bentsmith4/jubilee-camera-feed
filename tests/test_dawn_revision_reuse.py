"""Offline reuse tests with real local Git commits; no network or inference."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_current_forecast import snapshot, encode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
import verify_dawn_revisions as reuse

AS_OF = '2026-11-06T06:30:00-06:00'


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.state = snapshot()
        self.state['snapshot_time_ct'] = '2026-11-06T06:00:00-06:00'
        self.state['reconciliation']['as_of_utc'] = '2026-11-06T12:00:00+00:00'
        day = self.state['outlook'][0]
        self.state['outlook'] = [dict(day, date_ct='2026-11-' + str(n).zfill(2)) for n in (6, 7, 8)]
        self.raw = encode(self.state)
        self.forecast = encode(reuse.binding.project(self.raw))
        self.verifier = reuse.PairVerifier()

    def verify(self, raw=None, forecast=None, as_of=AS_OF):
        return self.verifier.verify(self.raw if raw is None else raw,
                                    self.forecast if forecast is None else forecast, as_of)

    def test_identical_pair_reuses_only_success_in_same_session(self):
        with patch.object(reuse.binding, 'check', wraps=reuse.binding.check) as check:
            self.assertFalse(self.verify()['binding_reused'])
            self.assertTrue(self.verify()['binding_reused'])
            self.assertEqual(check.call_count, 1)
        self.assertFalse(reuse.PairVerifier().verify(self.raw, self.forecast, AS_OF)['binding_reused'])

    def test_byte_change_requires_check_even_if_semantically_identical(self):
        self.verify()
        self.assertFalse(self.verify(forecast=self.forecast + b' ')['binding_reused'])
        with self.assertRaises(ValueError):
            self.verify(raw=self.raw + b' ')

    def test_new_observation_and_alerts_revalidate_with_same_probabilities(self):
        self.verify()
        for field in ('known_unknowns', 'direct_event_evidence_present', 'material_critical_input_fault'):
            state = copy.deepcopy(self.state)
            if field == 'known_unknowns':
                state[field].append('New observation requires scientific review')
            else:
                state['alert_gates'][field] = True
                state['alert_gates']['notification_suppressed'] = False
                state['notification_condition_met'] = True
            raw = encode(state)
            forecast = encode(reuse.binding.project(raw))
            self.assertFalse(self.verify(raw, forecast)['binding_reused'])

    def test_failures_never_enter_cache(self):
        for _ in range(2):
            with self.assertRaises(ValueError):
                self.verify(forecast=b'{}')
        self.assertFalse(self.verify()['binding_reused'])

    def test_rollover_future_and_naive_time_fail_even_after_hit(self):
        self.verify()
        for time in ('2026-11-07T00:00:00-06:00', '2026-11-06T05:59:00-06:00',
                     '2026-11-06T06:30:00'):
            with self.subTest(time=time), self.assertRaises(ValueError):
                self.verify(as_of=time)

    def test_production_season_boundaries_with_current_date_and_valid_horizon(self):
        for day, offset, allowed in (('2026-05-17', '-05:00', False),
                                     ('2026-05-18', '-05:00', True),
                                     ('2026-11-14', '-06:00', True),
                                     ('2026-11-15', '-06:00', False)):
            with self.subTest(day=day):
                state = copy.deepcopy(self.state)
                issue = day + 'T06:00:00' + offset
                state['snapshot_time_ct'] = issue
                state['reconciliation']['as_of_utc'] = issue
                start = datetime.fromisoformat(issue).date()
                template = state['outlook'][0]
                state['outlook'] = [dict(template, date_ct=(start + timedelta(days=n)).isoformat())
                                    for n in range(3)]
                raw = encode(state)
                forecast = encode(reuse.binding.project(raw))
                verifier = reuse.PairVerifier()
                if allowed:
                    self.assertFalse(verifier.verify(raw, forecast, issue)['binding_reused'])
                    self.assertTrue(verifier.verify(raw, forecast, issue)['binding_reused'])
                else:
                    with self.assertRaisesRegex(ValueError, 'outside production season'):
                        verifier.verify(raw, forecast, issue)

    def test_issue_valid_but_expired_horizon_rejected(self):
        self.state['outlook'][0]['date_ct'] = '2026-11-05'
        raw = encode(self.state)
        with self.assertRaisesRegex(ValueError, 'horizon'):
            self.verify(raw, encode(reuse.binding.project(raw)))

    def test_real_git_receipt_only_commit_and_validator_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return reuse.git(root, *args).decode().strip()
            git('init', '-q')
            git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Offline fixture')
            (root / 'model_data').mkdir()
            (root / reuse.binding.SNAPSHOT).write_bytes(self.raw)
            (root / reuse.binding.FORECAST).write_bytes(self.forecast)
            validator = root / 'model_data/bind_current_forecast.py'
            validator.write_bytes(Path(reuse.binding.__file__).read_bytes())
            git('add', '.')
            git('commit', '-qm', 'pair')
            first = git('rev-parse', 'HEAD')
            (root / 'receipt.md').write_text('append-only receipt')
            git('add', '.')
            git('commit', '-qm', 'receipt')
            result = reuse.verify_revisions(root, [first, 'HEAD'], AS_OF)
            self.assertEqual([r['binding_reused'] for r in result], [False, True])
            self.assertNotEqual(result[0]['commit'], result[1]['commit'])
            self.assertEqual(git('status', '--porcelain'), '')
            validator.write_bytes(validator.read_bytes() + b'\n')
            git('add', '.')
            git('commit', '-qm', 'validator changed')
            with self.assertRaisesRegex(ValueError, 'Validator differs'):
                reuse.verify_revisions(root, ['HEAD'], AS_OF)

    def test_workflow_runs_binding_once_with_horizon(self):
        workflow = (ROOT / '.github/workflows/forecast_consistency.yml').read_text()
        self.assertEqual(workflow.count('run: python -B model_data/bind_current_forecast.py --check'), 1)
        self.assertIn('--check --require-dawn-horizon', workflow)

    def test_windows_checkout_preserves_validator_identity_and_rejects_real_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return reuse.git(root, *args).decode().strip()
            git('init', '-q')
            git('config', 'user.email', 'fixture@example.invalid')
            git('config', 'user.name', 'Offline fixture')
            git('config', 'core.autocrlf', 'true')
            (root / 'model_data').mkdir()
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            (root / reuse.binding.SNAPSHOT).write_bytes(self.raw)
            (root / reuse.binding.FORECAST).write_bytes(self.forecast)
            validator = root / 'model_data/bind_current_forecast.py'
            validator.write_bytes(Path(reuse.binding.__file__).read_bytes())
            verifier = root / 'model_data/verify_dawn_revisions.py'
            verifier.write_bytes(Path(reuse.__file__).read_bytes())
            git('add', '.')
            git('commit', '-qm', 'Windows checkout fixture')
            commit = git('rev-parse', 'HEAD')
            # Force a real checkout so autocrlf conversion cannot be skipped.
            validator.unlink()
            verifier.unlink()
            git('checkout', '--', 'model_data/bind_current_forecast.py',
                'model_data/verify_dawn_revisions.py')
            self.assertEqual(validator.read_bytes(),
                             reuse.git(root, 'show', commit + ':model_data/bind_current_forecast.py'))
            command = [sys.executable, '-B', str(verifier), '--root', str(root),
                       '--as-of', AS_OF, commit, commit]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([r['binding_reused'] for r in json.loads(result.stdout)], [False, True])
            self.assertEqual(git('status', '--porcelain'), '')
            validator.write_bytes(validator.read_bytes() + b'\n# Unreviewed local change\n')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Validator differs', result.stderr)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()

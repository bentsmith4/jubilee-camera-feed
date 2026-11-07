"""Offline reuse tests with real local Git commits; no network or inference."""
import copy
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

    def test_rollover_future_naive_and_offseason_fail_even_after_hit(self):
        self.verify()
        for time in ('2026-11-07T00:00:00-06:00', '2026-11-06T05:59:00-06:00',
                     '2026-11-06T06:30:00', '2026-11-15T06:30:00-06:00'):
            with self.subTest(time=time), self.assertRaises(ValueError):
                self.verify(as_of=time)

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


if __name__ == '__main__':
    unittest.main()

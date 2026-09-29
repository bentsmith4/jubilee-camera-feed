"""Offline gates and idempotence; never publish a fixture receipt to GitHub."""
import copy
from datetime import timedelta
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import first_dawn_acceptance as dawn
import pr34_dawn_followup as f


def receipt(verdict='PASS'):
    # Use the real producer formatter, including date, marker and run binding.
    with patch.dict(os.environ, GITHUB_RUN_ID='1234'):
        body = dawn.markdown(dict(status=verdict, captures=[], errors=['CAMERA at 07:24:45 CDT failed']
                                 if verdict == 'FAIL' else []))
    return dict(id=99, body=body, user={'login': 'github-actions[bot]'},
                created_at=(dawn.END+timedelta(minutes=12)).isoformat(),
                html_url=f'https://github.com/{dawn.REPO}/issues/26#issuecomment-99')


def producer():
    return dict(id=1234, path=f.WORKFLOW, head_branch='main', event='push',
                repository={'full_name': dawn.REPO}, head_repository={'full_name': dawn.REPO},
                status='completed', conclusion='success')


def pr():
    return dict(merged=True, state='closed', merge_commit_sha=f.MERGE,
                head={'sha': f.PR_HEAD, 'repo': {'full_name': dawn.REPO}},
                base={'sha': 'a'*40, 'ref': 'main', 'repo': {'full_name': dawn.REPO}})


def checks():
    return [dict(name=name, app={'slug': 'github-actions'}, id=i, status='completed', conclusion='success',
                 details_url=f'https://github.com/{dawn.REPO}/actions/runs/{i}')
            for i, name in enumerate(f.CHECKS, 1)]


class Gates(unittest.TestCase):
    def test_old_deployment_pass_and_nonbot_marker_do_not_arm(self):
        old = dict(body='Final status: PASS\nActual PointClearPC deployment — 2026-09-28',
                   user={'login': 'bentsmith4'})
        forged = receipt()
        forged['user']['login'] = 'other-user'
        self.assertIsNone(f.terminal([old, forged]))

    def test_real_producer_terminal_receipts(self):
        for verdict in ('PASS', 'FAIL'):
            self.assertEqual(f.terminal([receipt(verdict)])[1], verdict)

    def test_pending_wrong_date_early_and_duplicate_are_blocked(self):
        for edit in ('pending', 'date', 'early', 'duplicate'):
            with self.subTest(edit=edit):
                c = receipt()
                if edit == 'pending':
                    c['body'] = c['body'].replace('acceptance: PASS', 'acceptance: PENDING')
                elif edit == 'date':
                    c['body'] = c['body'].replace('Target: September 29', 'Target: September 28')
                elif edit == 'early':
                    c['created_at'] = (dawn.END-timedelta(minutes=1)).isoformat()
                with self.assertRaises(ValueError):
                    f.terminal([c, c] if edit == 'duplicate' else [c])

    def test_producer_must_finish_and_match_event(self):
        api = Mock()
        run = producer()
        api.request.return_value = run
        api.pages.return_value = [{'steps': [{'name': 'Post exactly one final acceptance receipt to issue 26',
                                              'conclusion': 'success'}]}]
        self.assertTrue(f.validate_origin(api, receipt(), {'workflow_run': {'id': 1234}}))
        self.assertFalse(f.validate_origin(api, receipt(), {'workflow_run': {'id': 9000}}))
        self.assertFalse(f.validate_origin(api, receipt(), {'comment': {'id': 9000}}))
        run['status'] = 'in_progress'
        self.assertFalse(f.validate_origin(api, receipt(), {'comment': {'id': 99}}))

    def test_fork_wrong_workflow_and_unsuccessful_pass_block(self):
        for key, value in [('head_repository', {'full_name': 'other/fork'}),
                           ('path', '.github/workflows/other.yml'), ('conclusion', 'failure')]:
            api = Mock()
            api.request.return_value = dict(producer(), **{key: value})
            with self.assertRaises(ValueError):
                f.validate_origin(api, receipt(), {})

    def test_fail_producer_can_have_failed_conclusion(self):
        api = Mock()
        api.request.return_value = dict(producer(), conclusion='failure')
        api.pages.return_value = [{'steps': [{'name': 'Post exactly one final acceptance receipt to issue 26',
                                              'conclusion': 'success'}]}]
        self.assertTrue(f.validate_origin(api, receipt('FAIL'), {}))

    def test_exact_pr_and_latest_green_checks(self):
        api = Mock()
        api.request.return_value = pr()
        api.pages.return_value = checks()
        self.assertEqual(len(f.check_pr(api)[1]), 3)
        api.pages.return_value.append(dict(checks()[0], id=100, conclusion='failure'))
        with self.assertRaisesRegex(ValueError, 'not green'):
            f.check_pr(api)
        api.request.return_value['merged'] = False
        with self.assertRaisesRegex(ValueError, 'identity'):
            f.check_pr(api)

    def test_changed_source_or_missing_ancestry_blocks(self):
        with patch.object(dawn, 'ancestor', return_value=False):
            with self.assertRaisesRegex(ValueError, 'ancestry'):
                f.source_evidence(ROOT, 'b'*40, pr())
        with patch.object(dawn, 'ancestor', return_value=True), patch.object(dawn, 'blob', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'changed'):
                f.source_evidence(ROOT, 'b'*40, pr())


class Delivery(unittest.TestCase):
    def api(self, comments):
        api = Mock()
        api.pages.return_value = comments
        def request(path, body=None):
            if body is not None:
                api.saved = dict(body, id=100, html_url='https://github.com/example/receipt')
            return api.saved
        api.request.side_effect = request
        return api

    def test_pending_never_prepares_or_posts(self):
        api = self.api([])
        with patch.object(f, 'prepare') as prepare:
            f.run(ROOT, api, {})
            prepare.assert_not_called()
            api.request.assert_not_called()

    def test_fail_posts_exact_blocker_without_source_review(self):
        api = self.api([receipt('FAIL')])
        with patch.object(f, 'validate_origin', return_value=True), patch.object(f, 'prepare') as prepare:
            f.run(ROOT, api, {})
            prepare.assert_not_called()
            self.assertIn('07:24:45 CDT', api.saved['body'])
            self.assertNotIn('Get-FileHash', api.saved['body'])
            self.assertIn('No deployment package', api.saved['body'])

    def test_pass_delivers_then_repeated_event_is_noop(self):
        api = self.api([receipt()])
        with patch.object(f, 'validate_origin', return_value=True), patch.object(f, 'prepare', return_value='READY handoff') as prepare:
            f.run(ROOT, api, {})
            prepare.assert_called_once()
            self.assertIn('READY handoff', api.saved['body'])
        api.pages.return_value.append(dict(api.saved, user={'login': 'github-actions[bot]'}))
        api.request.reset_mock()
        with patch.object(f, 'prepare') as prepare:
            f.run(ROOT, api, {})
            prepare.assert_not_called()
            api.request.assert_not_called()

    def test_recheck_blocker_does_not_publish_partial_handoff(self):
        api = self.api([receipt()])
        with patch.object(f, 'validate_origin', return_value=True), patch.object(f, 'prepare', side_effect=ValueError('source changed')):
            f.run(ROOT, api, {})
        self.assertIn('source changed', api.saved['body'])
        self.assertNotIn('READY', api.saved['body'])

    def test_template_renders_hashes_rollback_and_no_manual_capture(self):
        rows = [dict(path=name, name=Path(name).name, sha256=f.EXPECTED[name], blob='d'*40,
                     previous_sha256='e'*64) for name in f.FILES]
        api = Mock()
        api.request.return_value = {'commit': {'sha': 'c'*40}}
        with patch.object(f, 'check_pr', return_value=(pr(), checks())), \
             patch.object(f, 'source_evidence', return_value=rows), \
             patch.object(f, 'observed_diagnostics', return_value='no diagnostics yet'), \
             patch.object(dawn, 'git', return_value=Mock(stdout=('c'*40).encode())):
            body = f.prepare(ROOT, api, receipt())
        for value in ('c'*40, *f.EXPECTED.values(), 'Rollback', 'No manual capture',
                      'BLOCKED_LOCAL_DIVERGENCE', 'DEPLOYED_PENDING_SCHEDULED_VERIFICATION',
                      '$ErrorActionPreference', 'Get-FileHash', 'three ordered shots'):
            self.assertIn(value, body)
        self.assertNotIn('$$', body)


if __name__ == '__main__':
    unittest.main()

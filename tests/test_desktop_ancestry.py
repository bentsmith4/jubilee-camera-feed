"""Production-shaped Git evidence: the publisher has not fetched newer main.

Only network transport is stubbed. Publication receipts, blobs, direct parents,
local ancestry and read-only fingerprints use real Git repositories.
"""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_desktop_verifier import Fixture, fingerprints, v


class AncestryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        production = self.root / 'production'
        production.mkdir()
        self.f = Fixture(production)
        self.f.git('remote', 'add', 'origin', v.CANONICAL_REPO + '.git')
        self.remote = self.root / 'github-main'
        subprocess.run(['git', 'clone', '--no-hardlinks', str(self.f.repo), str(self.remote)],
                       check=True, capture_output=True)
        self.remote_git('config', 'user.name', 'Acceptance Test')
        self.remote_git('config', 'user.email', 'test@example.invalid')
        self.remote_git('config', 'core.autocrlf', 'false')
        (self.remote / 'model.py').write_text('later reviewed main change\n')
        self.remote_git('add', 'model.py')
        self.remote_git('commit', '-m', 'reviewed update after publication')
        self.tip = self.remote_git('rev-parse', 'HEAD').strip()
        self.snapshot = self.f.snapshot()
        # Production may have staged and untracked work; verification must
        # preserve those bytes as well as FETCH_HEAD, refs, config and objects.
        (self.f.repo / 'model.py').write_text('staged production work\n')
        self.f.git('add', 'model.py')
        (self.f.repo / 'untracked.txt').write_text('private untracked work\n')

    def remote_git(self, *args):
        return subprocess.run(['git', '-C', str(self.remote), *args], check=True,
                              capture_output=True, text=True).stdout

    def comparison(self, ancestor, tip=None):
        tip = tip or self.tip
        ahead = int(self.remote_git('rev-list', '--count', ancestor + '..' + tip))
        behind = int(self.remote_git('rev-list', '--count', tip + '..' + ancestor))
        status = 'diverged' if ahead and behind else 'ahead' if ahead else 'behind' if behind else 'identical'
        return dict(url=f'{v.GITHUB_API_REPO}/compare/{ancestor}...{tip}',
                    base_commit={'sha': ancestor},
                    merge_base_commit={'sha': self.remote_git('merge-base', ancestor, tip).strip()},
                    ahead_by=ahead, behind_by=behind, total_commits=ahead, status=status,
                    # Deliberately empty: membership in a truncated commit page
                    # is not evidence of ancestry. Only compare metadata is.
                    commits=[])

    def run_publication(self, *, responses=None, tips=None, previous=None, full=False):
        tips = iter(tips or [self.tip, self.tip])
        git = v.git
        commands, requests, connections = [], [], []
        default = [self.comparison(self.f.previous), self.comparison(self.f.published)]
        responses = iter(default if responses is None else responses)

        def network_git(repo, *args):
            commands.append(args)
            if args[0] == 'ls-remote':
                self.assertIn(args[2], (v.CANONICAL_REPO, v.CANONICAL_REPO + '.git'))
                return 0, (next(tips) + '\trefs/heads/main\n').encode()
            return git(repo, *args)

        def connection_factory(host, **kwargs):
            self.assertEqual((host, kwargs), ('api.github.com', {'timeout': 10}))
            connection = Mock()
            connections.append(connection)

            def request(method, path, headers):
                requests.append((method, path, headers))
                self.assertEqual(method, 'GET')
                self.assertNotIn('Authorization', headers)
                self.assertTrue(path.endswith('?per_page=1&page=2'))

            connection.request.side_effect = request
            item = next(responses)
            if isinstance(item, Exception):
                connection.getresponse.side_effect = item
            else:
                status, body = item if isinstance(item, tuple) else (200, json.dumps(item).encode())
                response = Mock(status=status)
                response.read.side_effect = io.BytesIO(body).read
                connection.getresponse.return_value = response
            return connection

        before = fingerprints(self.f.root)
        with patch.object(v, 'git', side_effect=network_git), \
                patch.object(v.http.client, 'HTTPSConnection', side_effect=connection_factory) as network:
            if full:
                result = v.verify(self.f.root, self.f.inventory, now=self.f.now,
                                  client_factory=lambda root: (self.f.client, 'test-bucket'))
            else:
                result = v.checked(v.publication, self.f.root, self.snapshot, previous=previous)
        self.assertEqual(fingerprints(self.f.root), before)
        for connection in connections:
            connection.close.assert_called_once_with()
        self.assertTrue(all(command[0] in {'config', 'cat-file', 'rev-parse', 'diff-tree',
                                          'show', 'remote', 'ls-remote', 'merge-base'} for command in commands))
        return result, network.call_count, requests, commands

    def test_missing_local_tip_passes_without_injecting_objects(self):
        self.assertNotEqual(v.git(self.f.repo, 'cat-file', '-e', self.tip)[0], 0)
        report, calls, requests, commands = self.run_publication(full=True)
        self.assertEqual(report['status'], 'PASS', report)
        evidence = report['checks']['git_publication']
        self.assertEqual(evidence['ancestry_evidence'], 'github_compare')
        self.assertEqual(evidence['current_main'], self.tip)
        self.assertEqual(calls, 2)
        for request, ancestor in zip(requests, (self.f.previous, self.f.published)):
            self.assertIn(f'/compare/{ancestor}...{self.tip}?', request[1])
        self.assertEqual(sum(command[0] == 'ls-remote' for command in commands), 2)
        self.assertNotEqual(v.git(self.f.repo, 'cat-file', '-e', self.tip)[0], 0)

    def test_local_proof_does_not_call_github_api(self):
        result, calls, _, _ = self.run_publication(tips=[self.f.published] * 2)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['ancestry_evidence'], 'local_git')
        self.assertEqual(calls, 0)

    def test_moved_main_never_passes_with_old_compare_evidence(self):
        for responses in (None, [TimeoutError('PRIVATE_NETWORK_DIAGNOSTIC')]):
            with self.subTest(responses=responses):
                result, _, _, _ = self.run_publication(responses=responses, tips=[self.tip, 'a' * 40])
                self.assertEqual(result, v.result('NOT_VERIFIED', 'remote_main_changed_during_check'))

    def test_bad_explicit_parent_fails_before_remote_fallback(self):
        result, calls, _, commands = self.run_publication(previous=self.f.published)
        self.assertEqual(result, v.result('FAIL', 'prior_main_not_publication_parent'))
        self.assertEqual(calls, 0)
        self.assertFalse(any(command[0] == 'ls-remote' for command in commands))

    def test_replaced_fetch_head_remains_not_verified(self):
        (self.f.repo / '.git' / 'FETCH_HEAD').write_text(self.f.published + "\t\tbranch 'main' of remote\n")
        result, calls, _, _ = self.run_publication()
        self.assertEqual(result, v.result('NOT_VERIFIED', 'fetch_head_no_longer_publication_parent'))
        self.assertEqual(calls, 0)

    def test_unavailable_network_evidence_is_sanitized_and_not_verified(self):
        for response in (TimeoutError('PRIVATE_NETWORK_DIAGNOSTIC'), OSError('PRIVATE_NETWORK_DIAGNOSTIC'),
                         (403, b'PRIVATE_RATE_LIMIT'), (404, b'private'), (429, b'private'), (503, b'private'),
                         (302, b'redirect to private host'), (200, b'not JSON')):
            with self.subTest(response=type(response).__name__):
                result, calls, _, commands = self.run_publication(responses=[response])
                self.assertEqual(result, v.result('NOT_VERIFIED', 'github_ancestry_unavailable'))
                self.assertEqual(calls, 1)
                self.assertEqual(sum(command[0] == 'ls-remote' for command in commands), 2)

    def test_parent_proof_alone_cannot_pass_publication(self):
        result, calls, _, _ = self.run_publication(responses=[self.comparison(self.f.previous), (404, b'')])
        self.assertEqual(result['status'], 'NOT_VERIFIED')
        self.assertEqual(calls, 2)

    def test_inconclusive_or_wrong_comparison_cannot_pass(self):
        mutations = (
            lambda d: d.update(url=d['url'].replace(self.tip, 'a' * 40)),
            lambda d: d.update(url=d['url'].replace('bentsmith4', 'fork-owner')),
            lambda d: d.update(base_commit={'sha': self.f.published}),
            lambda d: d.update(merge_base_commit={'sha': self.tip}),
            lambda d: d.update(merge_base_commit=None),
            lambda d: d.update(status='behind'),
            lambda d: d.update(behind_by=1),
            lambda d: d.update(ahead_by=True),
            lambda d: d.pop('total_commits'),
        )
        for mutate in mutations:
            evidence = self.comparison(self.f.previous)
            mutate(evidence)
            with self.subTest(evidence=evidence):
                result, _, _, _ = self.run_publication(responses=[evidence])
                self.assertEqual(result, v.result('NOT_VERIFIED', 'github_ancestry_inconclusive'))
        for evidence in ([], {}, None, (200, b' ' * (v.GITHUB_COMPARE_BYTES + 1))):
            result, _, _, _ = self.run_publication(responses=[evidence])
            self.assertEqual(result, v.result('NOT_VERIFIED', 'github_ancestry_inconclusive'))

    def test_real_remote_divergence_is_fail_and_movement_is_not_verified(self):
        self.remote_git('checkout', '-b', 'diverged', self.f.previous)
        (self.remote / 'other.txt').write_text('unrelated main\n')
        self.remote_git('add', 'other.txt')
        self.remote_git('commit', '-m', 'main without publication')
        self.tip = self.remote_git('rev-parse', 'HEAD').strip()
        result, calls, _, _ = self.run_publication()
        self.assertEqual(result, v.result('FAIL', 'publication_not_on_current_main'))
        self.assertEqual(calls, 2)
        result, _, _, _ = self.run_publication(tips=[self.tip, 'a' * 40])
        self.assertEqual(result, v.result('NOT_VERIFIED', 'remote_main_changed_during_check'))

    def test_shallow_boundary_requires_conclusive_independent_evidence(self):
        # Import into the fixture during setup only, then mark the new tip as a
        # shallow boundary. Real Git returns 1 despite the true remote ancestry.
        self.f.git('fetch', str(self.remote), 'main')
        (self.f.repo / '.git' / 'FETCH_HEAD').write_text(self.f.previous + "\t\tbranch 'main' of remote\n")
        (self.f.repo / '.git' / 'shallow').write_text(self.tip + '\n')
        self.assertEqual(v.git(self.f.repo, 'merge-base', '--is-ancestor', self.f.published, self.tip)[0], 1)
        result, calls, _, _ = self.run_publication()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(calls, 2)
        for evidence in ((503, b''), {}):
            result, _, _, _ = self.run_publication(responses=[evidence])
            self.assertEqual(result['status'], 'NOT_VERIFIED')

    def test_noncanonical_remote_never_uses_fallback(self):
        for url in ('https://github.com/other/jubilee-camera-feed.git',
                    'http://github.com/bentsmith4/jubilee-camera-feed.git',
                    'https://github.com.evil.invalid/bentsmith4/jubilee-camera-feed'):
            self.f.git('remote', 'set-url', 'origin', url)
            result, calls, _, commands = self.run_publication()
            self.assertEqual(result, v.result('NOT_VERIFIED', 'remote_not_canonical_https'))
            self.assertEqual(calls, 0)
            self.assertFalse(any(command[0] == 'ls-remote' for command in commands))

    def test_publication_at_shallow_boundary_preserves_direct_parent_check(self):
        (self.f.repo / '.git' / 'shallow').write_text(self.f.published + '\n')
        self.assertEqual(self.f.git('rev-list', '--parents', '-n', '1', self.f.published).decode().split(),
                         [self.f.published])
        result, calls, _, _ = self.run_publication()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(calls, 2)
        result, _, _, _ = self.run_publication(previous=self.f.published)
        self.assertEqual(result, v.result('FAIL', 'prior_main_not_publication_parent'))

    def test_compare_status_consistency_for_identical_and_behind(self):
        ancestor = self.f.published
        for tip, expected in ((ancestor, 'PASS'), (self.f.previous, 'FAIL')):
            evidence = self.comparison(ancestor, tip)
            with patch.object(v, 'github_compare', return_value=evidence):
                try:
                    v.github_ancestor(ancestor, tip)
                    status = 'PASS'
                except v.EvidenceError as exc:
                    status = exc.status
            self.assertEqual(status, expected)


if __name__ == '__main__':
    unittest.main()

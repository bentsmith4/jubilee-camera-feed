"""Publish the state/forecast pair with bounded optimistic retries, never rebase it."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from publish_observation_record import git

OUTPUTS = ('model_data/current_state_snapshot.json', 'model_data/current_forecast.json')


def publish(repo, attempts=4, before_push=None, as_of=None):
    repo = repo.resolve()
    for attempt in range(attempts):
        git(repo, 'fetch', '--quiet', 'origin', 'refs/heads/main')
        parent = git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
        with tempfile.TemporaryDirectory(prefix='jubilee-current-state-') as td:
            checkout = Path(td) / 'checkout'
            git(repo, 'worktree', 'add', '--quiet', '--detach', str(checkout), parent)
            try:
                command = [sys.executable, '-B', str(checkout / 'model_data/reconcile_current_state.py'), '--root', str(checkout)]
                if as_of:
                    command += ['--as-of', as_of]
                # Execute the code AND read the evidence from the fetched generation.
                subprocess.run(command, cwd=checkout, check=True)
                changed = git(checkout, 'diff', '--name-only').stdout.decode().splitlines()
                if any(p not in OUTPUTS for p in changed):
                    raise ValueError('Reconciler changed a non-allowlisted path')
                if not changed:
                    # Even a no-op must recheck main; a publisher may have advanced it.
                    if before_push:
                        before_push(attempt)
                    git(repo, 'fetch', '--quiet', 'origin', 'refs/heads/main')
                    if git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip() == parent:
                        return dict(status='already_current', evidence_commit=parent, attempts=attempt+1)
                    continue
                if set(changed) != set(OUTPUTS):
                    raise ValueError('Snapshot and forecast must change together')
                git(checkout, 'add', '--', *OUTPUTS)
                git(checkout, 'commit', '--quiet', '-m', 'Reconcile current state with committed camera and sensing evidence')
                commit = git(checkout, 'rev-parse', 'HEAD').stdout.decode().strip()
                if before_push:
                    before_push(attempt)
                # A concurrent evidence/policy/state commit rejects this fast-forward.
                # Discard the candidate and rebuild BOTH files from the next main.
                if git(checkout, 'push', '--quiet', 'origin', commit + ':refs/heads/main', check=False).returncode == 0:
                    return dict(status='published', evidence_commit=parent, commit=commit, attempts=attempt+1)
            finally:
                git(repo, 'worktree', 'remove', '--force', str(checkout))
    raise RuntimeError('Concurrent update: bounded reconciliation retries exhausted; no force push or stale pair rebase')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--as-of', help='Deterministic offline replay clock')
    args = parser.parse_args()
    print(json.dumps(publish(args.repo, as_of=args.as_of)))

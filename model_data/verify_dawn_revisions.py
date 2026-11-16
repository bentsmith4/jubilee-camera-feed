"""Read-only binding reuse across pinned revisions, never scientific admission.

Only successful exact-byte pairs are memoized within this invocation. No disk
cache, restored CI cache, mutable ref identity, or probability-only shortcut.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

import bind_current_forecast as binding


class PairVerifier:
    def __init__(self):
        self._passed = set()

    def verify(self, snapshot_raw, forecast_raw, as_of):
        # These inexpensive temporal guards always execute, including cache hits.
        now = binding.aware_time(as_of).astimezone(binding.CT)
        snapshot = json.loads(snapshot_raw)
        issue = binding.aware_time(snapshot['snapshot_time_ct']).astimezone(binding.CT)
        binding.require(issue.date() == now.date() and issue <= now,
                        'Dawn verification requires a current-date, nonfuture snapshot')
        binding.require((5, 18) <= (now.month, now.day) <= (11, 14),
                        'Dawn production verification is outside production season')
        binding.require_dawn_horizon(snapshot)
        key = (snapshot_raw, forecast_raw)
        reused = key in self._passed
        if not reused:
            binding.check(snapshot_raw, json.loads(forecast_raw))
            self._passed.add(key)
        return {
            'scope': 'BINDING_ONLY_NOT_SOURCE_FRESHNESS_OR_SCIENTIFIC_ACCEPTANCE',
            'binding_reused': reused,
            'as_of': as_of,
            'snapshot_sha256': hashlib.sha256(snapshot_raw).hexdigest(),
            'forecast_sha256': hashlib.sha256(forecast_raw).hexdigest(),
        }


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def verify_revisions(root, revisions, as_of):
    verifier = PairVerifier()
    receipts = []
    for revision in revisions:
        # Resolve once; all subsequent reads use the immutable commit, not main.
        commit = git(root, 'rev-parse', '--verify', '--end-of-options',
                     revision + '^{commit}').decode().strip()
        validator = git(root, 'show', commit + ':model_data/bind_current_forecast.py')
        binding.require(validator == Path(binding.__file__).read_bytes(),
                        'Validator differs from pinned revision; run its reviewed validator')
        snapshot = git(root, 'show', commit + ':' + binding.SNAPSHOT)
        forecast = git(root, 'show', commit + ':' + binding.FORECAST)
        receipt = verifier.verify(snapshot, forecast, as_of)
        receipt.update(commit=commit, validator_sha256=hashlib.sha256(validator).hexdigest())
        receipts.append(receipt)
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=binding.ROOT)
    parser.add_argument('--as-of', help='Offset-aware review time; historical replay is not current acceptance')
    parser.add_argument('revisions', nargs='+')
    args = parser.parse_args()
    as_of = args.as_of or datetime.now(binding.CT).isoformat()
    try:
        receipts = verify_revisions(args.root, args.revisions, as_of)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Dawn revision verification FAIL: ' + str(error) + '\n')
    print(json.dumps(receipts, indent=2))


if __name__ == '__main__':
    main()

"""Validate a committed desktop receipt; admit only bounded operational context.

No desktop/R2 access, sensing, event labels, forecast inputs or alert decisions.
The archived issue comment and verifier report are attestations, not signatures
or substitutes for the private archive bytes. Git evidence is checked locally.
"""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess

import check_current_state_freshness as guard

RECEIPT = 'model_data/desktop_acceptance_20260928.json'
CAMERAS = tuple(sorted((
    'montrose_pier_boat', 'montrose_pier_bird', 'montrose_shoreline',
    'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth',
)))
METADATA = ('status.json', 'burst_status.json', 'vision.json')
FILES = tuple(sorted(METADATA + tuple(c + '.jpg' for c in CAMERAS)))
SOURCE = 'desktop_runtime/capture_service.py'
SCOPE = 'OPERATIONAL_ACCEPTANCE_ONLY'
MAX_MINUTES = 60  # Existing canonical acceptance ceiling, never receipt-controlled.


def require(condition, code):
    guard.require(condition, code)


def git(root, *args):
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_NO_REPLACE_OBJECTS='1',
               GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    p = subprocess.run(['git', '-C', str(root), *args], env=env, capture_output=True)
    require(p.returncode == 0, 'HISTORICAL_GIT_EVIDENCE_UNAVAILABLE_OR_MISMATCHED')
    return p.stdout


class HistoricalReader(guard.Reader):
    def __init__(self, root, commit):
        super().__init__(root)
        self.commit = commit

    def read(self, path):
        return git(self.root, 'show', self.commit + ':' + path)


def sha(value, length=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value),
            'INVALID_DIGEST_OR_COMMIT')
    return value


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('NONFINITE_JSON_VALUE')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def evidence(reader, ref):
    path = ref['path']
    require(isinstance(path, str) and re.fullmatch(r'model_data/desktop_acceptance_evidence/[A-Za-z0-9_./-]+', path)
            and '..' not in path.split('/'), 'INVALID_EVIDENCE_PATH')
    raw = reader.read(path)
    require(guard.digest(raw) == sha(ref['sha256']), 'EVIDENCE_HASH_MISMATCH')
    return raw


def validate(reader, receipt):
    """Validate historical claims without making them current or re-running acceptance."""
    require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1 and receipt['evidence_class'] == SCOPE,
            'UNSUPPORTED_RECEIPT_SCHEMA_OR_SCOPE')
    require(receipt['host'] == 'POINTCLEARPC' and receipt['status'] == 'PASS', 'NON_PASS_RECEIPT')
    require(type(receipt['production_weight']) is int and receipt['production_weight'] == 0
            and receipt['negative_event_label_allowed'] is False,
            'UNSAFE_RECEIPT_SCOPE')
    provenance = receipt['provenance']
    comment = provenance['issue_comment']
    require(comment['author'] == 'bentsmith4' and type(comment['id']) is int
            and comment['url'] == 'https://github.com/bentsmith4/jubilee-camera-feed/issues/26#issuecomment-' + str(comment['id']),
            'INVALID_ISSUE_PROVENANCE')
    body = evidence(reader, comment).decode('utf-8')
    require(body.startswith('Final status: PASS\n'), 'SOURCE_COMMENT_NOT_PASS')
    report = decode(evidence(reader, provenance['verifier_report']))
    require(report['schema_version'] == '3.0' and report['status'] == 'PASS'
            and report['scope'] == 'read_only_desktop_acceptance_existing_runtime', 'INVALID_VERIFIER_REPORT')
    require(report['side_effects'] == dict(camera_requests=False, publication_writes=False, runtime_modified=False),
            'VERIFIER_SIDE_EFFECTS')
    require(report['limits_minutes'] == dict(canonical=60, heartbeat=25, near_live=25), 'ACCEPTANCE_LIMIT_CHANGED')
    require(tuple(sorted(report['cameras'])) == CAMERAS, 'RECEIPT_CAMERA_SET_MISMATCH')
    require(all(v == dict(burst_frames=3, code='three_frames_and_vision_verified', status='PASS')
                for v in report['cameras'].values()), 'INCOMPLETE_CAMERA_ACCEPTANCE')
    checks = report['checks']
    codes = dict(capture='coherent_fresh_metadata', git_publication='append_only_publication_verified',
                 local_archive='local_manifest_and_bytes_verified', near_live='six_live_frames_verified',
                 r2_archive='r2_get_restore_verified', scheduled_tasks='coordinator_and_heartbeat_healthy',
                 snapshot_stability='capture_unchanged_during_check')
    require(set(checks) == set(codes) and all(checks[k]['status'] == 'PASS' and checks[k]['code'] == code
                                             for k, code in codes.items()), 'INCOMPLETE_ACCEPTANCE')
    require(checks['local_archive']['objects_verified'] == 27
            and checks['r2_archive']['objects_verified'] == 30
            and checks['r2_archive']['immutable_burst_frames'] == 18
            and checks['r2_archive']['restore_destination'] == 'memory_only'
            and checks['scheduled_tasks']['tasks_checked'] == 3
            and checks['scheduled_tasks']['canonical_in_season'] is True, 'ACCEPTANCE_COUNTS_OR_MODE_MISMATCH')
    capture = guard.stamp(checks['capture']['capture_time_utc'])
    checked = guard.stamp(report['checked_at_utc'])
    window = receipt['execution_window']
    start, end = (guard.stamp(window[k]) for k in ('started_at', 'completed_at'))
    available = guard.stamp(comment['updated_at'])
    require(capture <= start <= checked <= end <= guard.stamp(comment['created_at']) <= available,
            'INVALID_ACCEPTANCE_TIMELINE')
    require(checked - capture <= timedelta(minutes=MAX_MINUTES), 'STALE_AT_ACCEPTANCE')
    capture_id = checks['local_archive']['capture_id']
    require(re.fullmatch(r'\d{8}T\d{12}-[0-9a-f]{12}', capture_id) is not None
            and capture_id.startswith(datetime.fromisoformat(checks['capture']['capture_time_utc']).strftime('%Y%m%dT%H%M%S%f') + '-'),
            'INVALID_CAPTURE_ID')

    deployment = receipt['deployment']
    require(set(deployment) == {'reviewed_main_commit', 'pr_url', 'pr_head_commit', 'source_path',
                               'source_sha256', 'deployed_sha256', 'required_ancestors'}, 'INVALID_DEPLOYMENT_SCHEMA')
    require(isinstance(deployment['pr_url'], str) and re.fullmatch(
        r'https://github.com/bentsmith4/jubilee-camera-feed/pull/[1-9][0-9]*', deployment['pr_url']),
        'INVALID_PR_PROVENANCE')
    reviewed = sha(deployment['reviewed_main_commit'], 40)
    head = sha(deployment['pr_head_commit'], 40)
    require(deployment['source_path'] == SOURCE and deployment['deployed_sha256'] == sha(deployment['source_sha256']),
            'DEPLOYED_SOURCE_HASH_MISMATCH')
    source = git(reader.root, 'show', reviewed + ':' + SOURCE)
    require(guard.digest(source) == deployment['source_sha256'], 'REVIEWED_SOURCE_HASH_MISMATCH')
    require(set(deployment['required_ancestors']) == {'cadence', 'forecast_contract'}, 'MISSING_REQUIRED_ANCESTRY')
    for commit in [head, *deployment['required_ancestors'].values()]:
        git(reader.root, 'merge-base', '--is-ancestor', sha(commit, 40), reviewed)
    # A receipt from another history cannot certify this generation.
    git(reader.root, 'merge-base', '--is-ancestor', reviewed, reader.commit)
    publication = checks['git_publication']
    require(set(publication) == {'status', 'code', 'published_commit', 'previous_main',
                                'current_main', 'changed_path_count'}, 'INVALID_PUBLICATION_SCHEMA')
    pub, parent = (sha(publication[k], 40) for k in ('published_commit', 'previous_main'))
    require(publication['current_main'] == reviewed, 'REVIEWED_MAIN_MISMATCH')
    parents = git(reader.root, 'show', '-s', '--format=%P', pub).decode().strip().split()
    require(parents == [parent], 'PUBLICATION_PARENT_MISMATCH')
    git(reader.root, 'merge-base', '--is-ancestor', pub, reviewed)
    changed = git(reader.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', pub).decode().splitlines()
    require(sorted(changed) == receipt['publication_changed_paths'] and len(changed) == publication['changed_path_count']
            and set(changed) <= set(FILES) | {'api_usage_summary.json'}, 'PUBLICATION_PATHS_MISMATCH')
    require(set(receipt['published_files']) == set(FILES), 'PUBLISHED_HASH_SET_MISMATCH')
    historical = HistoricalReader(reader.root, pub)
    product = guard.camera_product(historical, checked)
    require(product['evidence_time'] == capture, 'CAPTURE_TIME_MISMATCH')
    docs = {p: historical.json(p) for p in METADATA}
    require(all(tuple(sorted(d['cameras'])) == CAMERAS for d in docs.values()), 'PUBLICATION_CAMERA_SET_MISMATCH')
    for camera in CAMERAS:
        require(docs['status.json']['cameras'][camera]['ok'] is True
                and docs['vision.json']['cameras'][camera]['burst_frame_count'] == 3
                and [s['shot'] for s in docs['burst_status.json']['cameras'][camera]['shots']] == [1, 2, 3],
                'PUBLICATION_CAMERA_NOT_ACCEPTED')
    for path, record in receipt['published_files'].items():
        raw = historical.read(path)
        require(guard.digest(raw) == sha(record['sha256'])
                and git(reader.root, 'rev-parse', pub + ':' + path).decode().strip() == sha(record['git_blob'], 40),
                'PUBLISHED_FILE_HASH_MISMATCH')
    # Check the machine fields against the archived public attestation as well
    # as Git. This is a reviewed evidence link, not authentication by text search.
    for value in (reviewed, head, pub, parent, deployment['source_sha256'], deployment['pr_url'], capture_id,
                  checks['capture']['capture_time_utc'], *CAMERAS, *deployment['required_ancestors'].values(),
                  'all 27 objects', '30 objects', '18 immutable burst frames', 'GET/hash/decode',
                  'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        require(value in body, 'SOURCE_ATTESTATION_MISMATCH')
    require(receipt['git_evidence_mode'] == 'process_only_alternate_object_directory'
            and receipt['default_verifier_status'] == 'NOT_VERIFIED', 'GIT_EVIDENCE_QUALIFICATION_MISSING')
    return dict(capture=capture, checked=checked, available=available, report=report)


def consume(reader, now, camera_minutes):
    """Missing, invalid, stale or mismatched evidence can never produce current PASS."""
    result = dict(status='NOT_VERIFIED', reason_codes=[], receipt_path=RECEIPT,
                  evidence_class=SCOPE, production_weight=0, negative_event_label_allowed=False,
                  historical_acceptance=None)
    try:
        if not git(reader.root, 'ls-tree', '--name-only', reader.commit, '--', RECEIPT).strip():
            result['reason_codes'] = ['MISSING_RECEIPT']
            return result
        receipt = decode(reader.read(RECEIPT))
        facts = validate(reader, receipt)
        report = facts['report']
        result['historical_acceptance'] = dict(
            status='PASS', host=receipt['host'], checked_at=report['checked_at_utc'],
            execution_window=receipt['execution_window'], available_at=receipt['provenance']['issue_comment']['updated_at'],
            capture_time=report['checks']['capture']['capture_time_utc'],
            capture_id=report['checks']['local_archive']['capture_id'], camera_ids=list(CAMERAS),
            local_objects_verified=27, r2_objects_verified=30, immutable_burst_frames=18,
            publication=report['checks']['git_publication'], deployment=receipt['deployment'],
            source_url=receipt['provenance']['issue_comment']['url'], receipt_sha256=guard.digest(reader.read(RECEIPT)),
            git_evidence_mode=receipt['git_evidence_mode'], default_verifier_status=receipt['default_verifier_status'],
            verification_basis='Committed/public hashes and ancestry checked; desktop/local/R2 results are archived execution attestations, not rerun here.')
        reasons = result['reason_codes']
        require(type(camera_minutes) in (int, float) and 0 < camera_minutes <= MAX_MINUTES,
                'UNSUPPORTED_CAMERA_FRESHNESS_POLICY')
        expires = facts['capture'] + timedelta(minutes=camera_minutes)
        result['valid_until_utc'] = expires.isoformat()
        if now < facts['available']:
            reasons.append('RECEIPT_NOT_YET_AVAILABLE')
        if now > expires:
            reasons.append('STALE_RECEIPT')
        registry = reader.json('model_data/camera_sources.json')
        ids = sorted(c['camera_id'] for c in registry['cameras'] if c['access'] == 'owner_google')
        if ids != list(CAMERAS):
            reasons.append('CURRENT_CAMERA_SET_MISMATCH')
        if guard.digest(reader.read(SOURCE)) != receipt['deployment']['source_sha256']:
            reasons.append('CURRENT_SOURCE_HASH_MISMATCH')
        if any(guard.digest(reader.read(p)) != record['sha256'] for p, record in receipt['published_files'].items()):
            reasons.append('CURRENT_CAPTURE_BINDING_MISMATCH')
        if not reasons:
            result['status'] = 'PASS'
        return result
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        # No arbitrary exception text or partially trusted PASS enters state.
        result['historical_acceptance'] = None
        result['reason_codes'] = ['INVALID_OR_UNVERIFIABLE_RECEIPT']
        if isinstance(exc, ValueError) and re.fullmatch('[A-Z_]+', str(exc)):
            result['reason_codes'].append(str(exc))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    reader = guard.Reader(args.root)
    reader.commit = git(args.root, 'rev-parse', 'HEAD').decode().strip()
    receipt = decode(reader.read(RECEIPT))
    facts = validate(reader, receipt)
    # Audit the available public JPEG bytes too; no private burst/R2 retrieval.
    import io
    from PIL import Image
    publication = facts['report']['checks']['git_publication']['published_commit']
    for camera in CAMERAS:
        raw = git(args.root, 'show', publication + ':' + camera + '.jpg')
        with Image.open(io.BytesIO(raw)) as image:
            require(image.format == 'JPEG', 'INVALID_PUBLIC_JPEG')
            image.load()
    print('PASS: receipt provenance, source SHA-256, public metadata/image hashes and decode, '
          'publication paths and ancestry; private local/R2 verification retained as attested history.')


if __name__ == '__main__':
    main()

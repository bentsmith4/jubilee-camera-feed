"""Read-only acceptance of the existing desktop; invoked by desktop_preflight.ps1.

Never import capture/publish/upload entry points: some execute on import. Reports
contain only constants, validated timestamps/SHA values, counts and booleans.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop_runtime'))
from archive_integrity import VerifiedStore
from camera_policy import CAMERA_IDS
from seasonal_policy import in_season
from PIL import Image

METADATA = ('status.json', 'burst_status.json', 'vision.json')
SHA = re.compile(r'[0-9a-f]{40}')
CAPTURE_MINUTES = 60  # Same bound as archive_integrity.freeze/publish_github.payload.
HEARTBEAT_MINUTES = 25  # 900s canonical + 300s live + 90s upload + margin.
LIVE_MINUTES = 25
FUTURE_SKEW = timedelta(minutes=2)


class EvidenceError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def require(condition, code, status='FAIL'):
    if not condition:
        raise EvidenceError(status, code)


def result(status, code, **details):
    return dict(status=status, code=code, **details)


def checked(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except EvidenceError as exc:
        return result(exc.status, exc.code)
    except FileNotFoundError:
        return result('NOT_VERIFIED', 'required_evidence_missing')
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return result('FAIL', 'invalid_evidence_schema')
    except Exception:
        # No exception text, paths, URLs, command output or SDK diagnostics.
        return result('NOT_VERIFIED', 'evidence_unavailable')


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, 'timezone_missing')
    return parsed


def fresh(value, now, minutes):
    parsed = timestamp(value)
    require(-FUTURE_SKEW <= now - parsed <= timedelta(minutes=minutes),
            'stale_or_future_timestamp')
    return parsed


def digest(content):
    return hashlib.sha256(content).hexdigest()


def read_file(root, relative):
    # Names supplied by this verifier, not paths in manifests; reject symlink escapes.
    root = root.resolve()
    path = root / relative
    require(path.resolve().is_relative_to(root), 'path_outside_evidence_root')
    return path.read_bytes()


def document(content):
    obj = json.loads(content.decode('utf-8-sig'))
    require(isinstance(obj, dict), 'invalid_document')
    return obj


def jpeg(content):
    try:
        with Image.open(io.BytesIO(content)) as image:
            require(image.format == 'JPEG', 'invalid_jpeg')
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()  # Decode as well as checking the container.
    except (OSError, ValueError, SyntaxError):
        raise EvidenceError('FAIL', 'invalid_jpeg') from None


class Snapshot:
    def __init__(self, root):
        self.root = root
        self.blobs = {}
        self.docs = {}
        self.capture = None
        self.capture_id = None
        self.hashes = {}

    def read(self, name):
        content = read_file(self.root, 'frames/' + name)
        self.blobs[name] = content
        return content

    def load(self, now):
        self.docs = {name: document(self.read(name)) for name in METADATA}
        self.capture = self.docs['status.json']['capture_time_ct']
        captured = fresh(self.capture, now, CAPTURE_MINUTES)
        for doc in self.docs.values():
            require(doc.get('capture_time_ct') == self.capture, 'capture_identity_mismatch')
            require(set(doc.get('cameras', {})) == set(CAMERA_IDS), 'six_camera_set_mismatch')
        # Older products have no capture_id; if present it must agree in all three.
        ids = [doc.get('capture_id') for doc in self.docs.values()]
        require(not any(ids) or (all(ids) and len(set(ids)) == 1), 'capture_id_mismatch')
        return result('PASS', 'coherent_fresh_metadata', capture_time_utc=captured.astimezone(timezone.utc).isoformat())

    def camera(self, camera, now):
        status = self.docs['status.json']['cameras'].get(camera, {})
        burst = self.docs['burst_status.json']['cameras'].get(camera, {})
        vision = self.docs['vision.json']['cameras'].get(camera, {})
        require(status.get('ok') is True and burst.get('ok') is True, 'camera_capture_failed_or_missing')
        require(vision.get('status') == 'ok', 'camera_vision_failed_or_missing')
        require(status.get('burst_count') == 3 and vision.get('burst_frame_count') == 3,
                'incomplete_three_frame_result')
        shots = burst.get('shots', [])
        require(len(shots) == 3 and [s.get('shot') for s in shots] == [1, 2, 3], 'invalid_shot_sequence')
        times = [fresh(s['timestamp_ct'], now, CAPTURE_MINUTES) for s in shots]
        require(times == sorted(times) and len(set(times)) == 3, 'invalid_shot_timing')
        require(times[0] >= timestamp(self.capture) - FUTURE_SKEW, 'shot_predates_capture')
        require(status.get('timestamp_ct') == shots[-1]['timestamp_ct'], 'latest_shot_timestamp_mismatch')
        expected_timing = [{k: shot.get(k) for k in ('shot', 'timestamp_ct', 'timing')} for shot in shots]
        require(vision.get('burst_shots') == expected_timing, 'vision_shot_identity_mismatch')
        for shot in shots:
            require(shot.get('timing') in ('actual_screenshot_time', 'nominal_interval_single_stream'),
                    'shot_timing_label_missing')
            content = self.read(f'burst_latest/{camera}_{shot["shot"]}.jpg')
            require(type(shot.get('bytes')) is int and len(content) == shot['bytes'], 'shot_size_mismatch')
            jpeg(content)
        latest = self.read(camera + '.jpg')
        jpeg(latest)
        require(len(latest) == status.get('bytes'), 'latest_size_mismatch')
        require(latest == self.blobs[f'burst_latest/{camera}_3.jpg'], 'latest_not_third_shot')
        return result('PASS', 'three_frames_and_vision_verified', burst_frames=3)

    def archive(self):
        # Exactly the same digest/name contract as freeze(), without calling it.
        require(len(self.blobs) == 27, 'complete_six_camera_snapshot_required', 'NOT_VERIFIED')
        combined = hashlib.sha256(b''.join(k.encode() + v for k, v in sorted(self.blobs.items()))).hexdigest()
        self.capture_id = timestamp(self.capture).strftime('%Y%m%dT%H%M%S%f') + '-' + combined[:12]
        self.hashes = {name: digest(content) for name, content in self.blobs.items()}
        folder = 'captures/' + self.capture_id + '/'
        raw_seal = read_file(self.root, folder + 'capture_manifest.json')
        seal = document(raw_seal)
        require(seal.get('capture_id') == self.capture_id and seal.get('capture_time_ct') == self.capture,
                'local_manifest_identity_mismatch')
        require(isinstance(seal.get('sha256'), dict), 'local_original_hashes_missing', 'NOT_VERIFIED')
        require(seal['sha256'] == self.hashes, 'local_manifest_hash_set_mismatch')
        for name, expected in self.hashes.items():
            require(digest(read_file(self.root, folder + name)) == expected, 'local_archive_hash_mismatch')
        require(read_file(self.root, folder + 'capture_manifest.json') == raw_seal,
                'local_manifest_changed_during_check', 'NOT_VERIFIED')
        return result('PASS', 'local_manifest_and_bytes_verified', capture_id=self.capture_id, objects_verified=len(self.hashes))

    def stable(self):
        require(bool(self.blobs), 'snapshot_missing', 'NOT_VERIFIED')
        require(all(read_file(self.root, 'frames/' + name) == content for name, content in self.blobs.items()),
                'capture_changed_during_check', 'NOT_VERIFIED')
        return result('PASS', 'capture_unchanged_during_check')


def task_health(root, inventory, now):
    require(isinstance(inventory, dict) and inventory.get('available') is True,
            'task_inventory_unavailable', 'NOT_VERIFIED')
    rows = inventory.get('tasks', [])
    owners = [row for row in rows if row.get('role') == 'coordinator']
    require(len(owners) == 1, 'expected_one_coordinator')
    owner = owners[0]
    require(owner.get('state') == 'Running', 'coordinator_not_running')
    if owner.get('enabled') is not True or owner.get('action_matches') is not True:
        return result('FAIL', 'coordinator_definition_mismatch', task_enabled=owner.get('enabled') is True,
                      action_matches=owner.get('action_matches') is True)
    # Microsoft SCHED_S_TASK_RUNNING is informational, not a failed exit code.
    require(owner.get('last_result') in (0, 0x41301), 'coordinator_last_result_failed')
    require(type(owner.get('missed_runs')) is int and owner['missed_runs'] == 0, 'missed_task_runs')
    require(timestamp(owner['last_run']) <= now + FUTURE_SKEW and timestamp(owner['last_run']).year >= 2020,
            'invalid_task_last_run')
    for row in rows:
        if row is not owner:
            require(row.get('enabled') is False and row.get('state') == 'Disabled', 'additional_capture_task_enabled')
    state = document(read_file(root, 'capture_service_state.json'))
    fresh(state['heartbeat'], now, HEARTBEAT_MINUTES)
    fresh(state['last_live_success'], now, LIVE_MINUTES)
    if in_season(now):
        fresh(state['last_canonical_success'], now, CAPTURE_MINUTES)
        require(state.get('canonical_monitoring_status') in ('scheduled', 'completed'), 'canonical_monitoring_state_mismatch')
    else:
        require(state.get('canonical_monitoring_status') == 'offseason_not_monitored', 'seasonal_state_mismatch')
    return result('PASS', 'coordinator_and_heartbeat_healthy', tasks_checked=len(rows),
                  canonical_in_season=in_season(now))


def live_health(root, now):
    raw = read_file(root, 'live_frames/status.json')
    doc = document(raw)
    blobs = {'status.json': raw}
    captured = fresh(doc['capture_time_ct'], now, LIVE_MINUTES)
    require(set(doc.get('cameras', {})) == set(CAMERA_IDS), 'live_six_camera_set_mismatch')
    for camera in CAMERA_IDS:
        cam = doc['cameras'][camera]
        require(cam.get('ok') is True, 'live_camera_failed')
        require(fresh(cam['timestamp_ct'], now, LIVE_MINUTES) >= captured - FUTURE_SKEW, 'live_camera_identity_mismatch')
        content = read_file(root, 'live_frames/' + camera + '.jpg')
        blobs[camera + '.jpg'] = content
        require(len(content) == cam.get('bytes'), 'live_size_mismatch')
        jpeg(content)
    require(all(read_file(root, 'live_frames/' + name) == content for name, content in blobs.items()),
            'live_changed_during_check', 'NOT_VERIFIED')
    return result('PASS', 'six_live_frames_verified')


def git(repo, *args):
    env = os.environ.copy()
    # No index refresh, pager, terminal prompt, credential-helper persistence or
    # protocol helper for an arbitrary URL in local config. All diagnostics stay private.
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1',
               GIT_NO_LAZY_FETCH='1', GIT_ASKPASS='')
    command = ['git', '--no-pager', '-c', 'credential.helper=', '-c', 'core.fsmonitor=false',
               '-c', 'core.hooksPath=', '-c', 'core.askPass=', '-c', 'protocol.allow=never',
               '-c', 'protocol.https.allow=always', '-C', str(repo), *args]
    proc = subprocess.run(command, capture_output=True, env=env, timeout=20)
    return proc.returncode, proc.stdout


def git_value(repo, *args):
    code, value = git(repo, *args)
    require(code == 0, 'git_evidence_unavailable', 'NOT_VERIFIED')
    return value


def remote_tip(repo):
    url = git_value(repo, 'remote', 'get-url', 'origin').decode().strip()
    require(url in ('https://github.com/bentsmith4/jubilee-camera-feed.git',
                    'https://github.com/bentsmith4/jubilee-camera-feed'),
            'remote_not_canonical_https', 'NOT_VERIFIED')
    raw = git_value(repo, 'ls-remote', '--exit-code', url, 'refs/heads/main').decode().strip()
    fields = raw.split()
    require(len(fields) == 2 and SHA.fullmatch(fields[0]) and fields[1] == 'refs/heads/main',
            'remote_main_unavailable', 'NOT_VERIFIED')
    return fields[0]


def publication(root, snapshot, published=None, previous=None, offline=False):
    repo = root / 'jubilee-camera-feed'
    if published is None:
        # Bounded tail; never echo log lines, even if a child once logged a secret.
        with (root / 'capture_service.log').open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 262144))
            receipts = re.findall(rb'GITHUB APPEND-ONLY PUBLISH SUCCESS: ([0-9a-f]{40})(?:\r?\n|$)', stream.read())
        require(bool(receipts), 'publication_receipt_missing', 'NOT_VERIFIED')
        published = receipts[-1].decode()
    require(SHA.fullmatch(published) is not None, 'invalid_publication_sha')
    # Partial clones may fetch implicitly on older Git versions even for a
    # read command. Refuse them in addition to GIT_NO_LAZY_FETCH on newer Git.
    _, promisor = git(repo, 'config', '--get-regexp', r'^(extensions\.partialclone|remote\..*\.promisor)$')
    require(not promisor.strip(), 'partial_clone_requires_existing_full_history', 'NOT_VERIFIED')
    parents = git_value(repo, 'rev-list', '--parents', '-n', '1', published).decode().split()
    require(len(parents) == 2 and parents[0] == published, 'publication_not_single_parent')
    parent = parents[1]
    inferred_previous = previous is None
    if inferred_previous:
        fetch_path = Path(git_value(repo, 'rev-parse', '--git-path', 'FETCH_HEAD').decode().strip())
        if not fetch_path.is_absolute():
            fetch_path = repo / fetch_path
        records = fetch_path.read_text(encoding='utf-8').splitlines()
        candidates = [line.split('\t')[0] for line in records if "branch 'main' of " in line]
        require(len(candidates) == 1 and SHA.fullmatch(candidates[0]), 'prior_main_evidence_missing', 'NOT_VERIFIED')
        previous = candidates[0]
    require(SHA.fullmatch(previous) is not None, 'invalid_previous_main_sha')
    require(previous == parent, 'fetch_head_no_longer_publication_parent' if inferred_previous else 'prior_main_not_publication_parent',
            'NOT_VERIFIED' if inferred_previous else 'FAIL')
    # A whole-tree diff also proves model/config/history files were preserved.
    paths = git_value(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', parent, published).decode().split('\0')
    paths = set(filter(None, paths))
    allowed = set(METADATA) | {camera + '.jpg' for camera in CAMERA_IDS} | {'api_usage_summary.json'}
    require(bool(paths) and paths <= allowed, 'publication_changed_nonallowlisted_paths')
    for name in METADATA + tuple(camera + '.jpg' for camera in CAMERA_IDS):
        require(git_value(repo, 'show', published + ':' + name) == snapshot.blobs[name], 'published_capture_bytes_mismatch')
    details = dict(published_commit=published, previous_main=previous, changed_path_count=len(paths))
    if offline:
        return result('NOT_VERIFIED', 'remote_main_check_disabled', local_contract='PASS', **details)
    tip = remote_tip(repo)
    # Do not fetch. Missing objects and shallow histories are explicitly inconclusive.
    git_value(repo, 'cat-file', '-e', tip + '^{commit}')
    for ancestor in (previous, published):
        code, _ = git(repo, 'merge-base', '--is-ancestor', ancestor, tip)
        if code == 1:
            shallow = git_value(repo, 'rev-parse', '--is-shallow-repository').strip() == b'true'
            require(False, 'shallow_history_inconclusive' if shallow else 'publication_not_on_current_main',
                    'NOT_VERIFIED' if shallow else 'FAIL')
        require(code == 0, 'git_ancestry_unavailable', 'NOT_VERIFIED')
    require(remote_tip(repo) == tip, 'remote_main_changed_during_check', 'NOT_VERIFIED')
    return result('PASS', 'append_only_publication_verified', current_main=tip, **details)


def r2_client(root):
    path = root / 'r2.json'
    require(path.is_file(), 'r2_credentials_unavailable', 'NOT_VERIFIED')
    cfg = document(path.read_bytes())
    require(all(isinstance(cfg.get(k), str) and cfg[k] for k in ('endpoint', 'access_key', 'secret_key')),
            'r2_config_incomplete', 'NOT_VERIFIED')
    endpoint = urlsplit(cfg['endpoint'])
    require(endpoint.scheme == 'https' and endpoint.hostname is not None and
            endpoint.hostname.endswith('.r2.cloudflarestorage.com') and
            endpoint.username is None and endpoint.password is None and not endpoint.query and
            not endpoint.fragment and endpoint.path in ('', '/') and endpoint.port in (None, 443),
            'r2_endpoint_invalid', 'NOT_VERIFIED')
    # No environment/instance-profile credential chain and no HTTP debug logging.
    import boto3
    from botocore.config import Config
    client = boto3.client('s3', endpoint_url=cfg['endpoint'].rstrip('/'),
                          aws_access_key_id=cfg['access_key'], aws_secret_access_key=cfg['secret_key'],
                          region_name='auto', config=Config(connect_timeout=5, read_timeout=10,
                          retries={'total_max_attempts': 1}))
    return client, cfg.get('bucket', 'jubilee-cameras')


def get_bytes(client, bucket, key):
    body = client.get_object(Bucket=bucket, Key=key)['Body']
    try:
        return body.read()
    finally:
        body.close()


def r2_archive(root, snapshot, offline=False, client_factory=r2_client):
    if offline:
        return result('NOT_VERIFIED', 'r2_readback_disabled')
    require(bool(snapshot.hashes), 'local_archive_required', 'NOT_VERIFIED')
    client, bucket = client_factory(root)
    pointer = get_bytes(client, bucket, 'archive/latest_manifest.json')
    store = VerifiedStore(client)
    try:
        manifest = document(pointer)
        require(manifest.get('capture_id') == snapshot.capture_id and manifest.get('capture_time_ct') == snapshot.capture,
                'r2_manifest_identity_mismatch')
        prefix = timestamp(snapshot.capture).strftime('archive/%Y-%m-%d/%H%M%S')
        require(manifest.get('archive_prefix') == prefix, 'r2_prefix_mismatch')
        require(isinstance(manifest.get('local_capture_sha256'), dict) and isinstance(manifest.get('sha256'), dict),
                'r2_original_hashes_missing', 'NOT_VERIFIED')
        require(manifest.get('local_capture_sha256') == snapshot.hashes, 'r2_local_manifest_mismatch')
        expected = {}
        for name, sha in snapshot.hashes.items():
            if name.startswith('burst_latest/'):
                expected[prefix + '/burst/' + name.split('/')[1]] = sha
            elif name != 'status.json':
                expected[name] = sha
                if name in METADATA:
                    expected[prefix + '/' + name] = sha
        require(manifest.get('sha256') == expected, 'r2_object_hash_set_mismatch')
        require(set(manifest.get('cameras', {})) == set(CAMERA_IDS), 'r2_six_camera_set_mismatch')
        for camera in CAMERA_IDS:
            cam = manifest['cameras'][camera]
            source = snapshot.docs['status.json']['cameras'][camera]
            require(cam.get('ok') is True and cam.get('timestamp_ct') == source['timestamp_ct'] and
                    cam.get('bytes') == source['bytes'] and cam.get('latest_key') == camera + '.jpg',
                    'r2_camera_manifest_mismatch')
            shots = cam.get('burst', [])
            require(len(shots) == 3 and [shot.get('shot') for shot in shots] == [1, 2, 3], 'r2_burst_incomplete')
            for shot, original in zip(shots, snapshot.docs['burst_status.json']['cameras'][camera]['shots']):
                require(all(shot.get(k) == original.get(k) for k in ('shot', 'timestamp_ct', 'timing', 'bytes')) and
                        shot.get('archive_key') == f'{prefix}/burst/{camera}_{shot["shot"]}.jpg',
                        'r2_shot_manifest_mismatch')
        expected[prefix + '/manifest.json'] = digest(pointer)
        expected['status.json'] = snapshot.hashes['status.json']
        for key, sha in expected.items():
            try:
                content = store.read_verified(bucket, key, sha)
            except ValueError:
                raise EvidenceError('FAIL', 'r2_readback_hash_mismatch') from None
            if key.endswith('.jpg'):
                jpeg(content)
        verdict = result('PASS', 'r2_get_restore_verified', objects_verified=len(expected),
                         immutable_burst_frames=18, restore_destination='memory_only')
    except Exception as exc:
        # Prefer a concurrent-update result when latest advanced during read-back.
        if get_bytes(client, bucket, 'archive/latest_manifest.json') != pointer:
            return result('NOT_VERIFIED', 'r2_pointer_changed_during_check')
        raise exc
    require(get_bytes(client, bucket, 'archive/latest_manifest.json') == pointer,
            'r2_pointer_changed_during_check', 'NOT_VERIFIED')
    return verdict


def verify(root, inventory, now=None, offline=False, published=None, previous=None, client_factory=r2_client):
    now = now or datetime.now(timezone.utc)
    snapshot = Snapshot(root)
    checks = {'scheduled_tasks': checked(task_health, root, inventory, now),
              'near_live': checked(live_health, root, now)}
    checks['capture'] = checked(snapshot.load, now)
    cameras = {camera: checked(snapshot.camera, camera, now) for camera in CAMERA_IDS}
    complete = checks['capture']['status'] == 'PASS' and all(row['status'] == 'PASS' for row in cameras.values())
    blocked = result('NOT_VERIFIED', 'complete_current_capture_required')
    checks['local_archive'] = checked(snapshot.archive) if complete else dict(blocked)
    checks['git_publication'] = checked(publication, root, snapshot, published, previous, offline) if complete else dict(blocked)
    checks['r2_archive'] = (checked(r2_archive, root, snapshot, offline, client_factory)
                            if checks['local_archive']['status'] == 'PASS' else dict(blocked))
    checks['snapshot_stability'] = checked(snapshot.stable)
    if checks['snapshot_stability']['status'] != 'PASS':
        # A running capture can replace products while we inspect; no acceptance
        # claim about a torn snapshot. Keep task/live findings independently useful.
        for name in ('capture', 'local_archive', 'git_publication', 'r2_archive'):
            checks[name] = result('NOT_VERIFIED', 'capture_changed_or_unavailable_during_check')
        cameras = {camera: result('NOT_VERIFIED', 'capture_changed_or_unavailable_during_check') for camera in CAMERA_IDS}
    statuses = [row['status'] for row in list(checks.values()) + list(cameras.values())]
    overall = 'FAIL' if 'FAIL' in statuses else 'NOT_VERIFIED' if 'NOT_VERIFIED' in statuses else 'PASS'
    return dict(schema_version='3.0', scope='read_only_desktop_acceptance_existing_runtime',
                checked_at_utc=now.astimezone(timezone.utc).isoformat(), status=overall,
                limits_minutes=dict(canonical=CAPTURE_MINUTES, heartbeat=HEARTBEAT_MINUTES, near_live=LIVE_MINUTES),
                side_effects=dict(runtime_modified=False, camera_requests=False, publication_writes=False),
                checks=checks, cameras=cameras)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tasks-stdin', action='store_true')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--published-commit')
    parser.add_argument('--previous-main')
    args = parser.parse_args()
    try:
        inventory = json.load(sys.stdin) if args.tasks_stdin else None
        report = verify(args.root, inventory, offline=args.offline,
                        published=args.published_commit, previous=args.previous_main)
    except Exception:
        report = result('NOT_VERIFIED', 'verifier_input_unavailable')
    print(json.dumps(report, indent=2, sort_keys=True))
    return {'PASS': 0, 'FAIL': 1, 'NOT_VERIFIED': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())

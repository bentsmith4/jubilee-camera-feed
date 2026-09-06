"""Append-only, allowlisted camera publication; never edits the working tree."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(r'C:\JubileeCams')
from camera_policy import CAMERA_IDS as CAMERAS
METADATA = ('status.json', 'vision.json', 'burst_status.json')

def git(repo, *args, env=None, data=None, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], input=data,
                            capture_output=True, env=env)
    if check and result.returncode:
        raise RuntimeError('Git operation failed: ' + args[0] + ' (diagnostics suppressed)')
    return result

def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt

def validate_private(value):
    if isinstance(value, dict):
        if isinstance(value.get('cameras'), dict) and set(value['cameras']) - set(CAMERAS):
            raise ValueError('Unapproved camera metadata: publication refused')
        for key, item in value.items():
            if key.lower() in {'device_id', 'resource_name', 'access_token', 'refresh_token', 'answersdp', 'offersdp'}:
                raise ValueError('Private metadata: publication refused')
            validate_private(item)
    elif isinstance(value, list):
        for item in value:
            validate_private(item)
    elif isinstance(value, str) and any(x in value.lower() for x in ('rtsp://', 'rtsps://', 'bearer ', 'streamextensiontoken', '/enterprises/')):
        raise ValueError('Private stream data: publication refused')

def payload(base):
    frames = base / 'frames'
    raw = {name: (frames / name).read_bytes() for name in METADATA}
    docs = {name: json.loads(value.decode('utf-8-sig')) for name, value in raw.items()}
    status = docs['status.json']
    now = datetime.now(timezone.utc)
    captured = timestamp(status['capture_time_ct'])
    if not -timedelta(minutes=2) <= now - captured <= timedelta(minutes=60):
        raise ValueError('Capture stale or in the future')
    for doc in docs.values():
        validate_private(doc)
        if doc.get('capture_time_ct') != status['capture_time_ct']:
            raise ValueError('Capture metadata mismatch')
    for camera in CAMERAS:
        info = status.get('cameras', {}).get(camera, {})
        name = camera + '.jpg'
        raw[name] = None
        if info.get('ok') is True:
            age = now - timestamp(info['timestamp_ct'])
            if not -timedelta(minutes=2) <= age <= timedelta(minutes=60):
                raise ValueError('Camera timestamp stale or in the future')
            content = (frames / name).read_bytes()
            if not content.startswith(b'\xff\xd8') or not content.endswith(b'\xff\xd9'):
                raise ValueError('Invalid JPEG')
            raw[name] = content
    return raw, captured

def publish(base=BASE, attempts=3, before_push=None):
    repo = base / 'jubilee-camera-feed'
    files, captured = payload(base)
    with tempfile.TemporaryDirectory(prefix='jubilee-publish-') as temp:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(temp) / 'index')
        for attempt in range(attempts):
            git(repo, 'fetch', '--quiet', 'origin', 'refs/heads/main')
            parent = git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
            prior = git(repo, 'show', parent + ':status.json', check=False)
            if prior.returncode == 0:
                prior_time = json.loads(prior.stdout.decode('utf-8-sig')).get('capture_time_ct')
                if prior_time and timestamp(prior_time) > captured:
                    raise ValueError('Remote camera snapshot is newer')
            git(repo, 'read-tree', parent, env=env)
            for name, content in files.items():
                if content is None:
                    git(repo, 'update-index', '--force-remove', '--', name, env=env)
                else:
                    blob = git(repo, 'hash-object', '-w', '--stdin', data=content).stdout.decode().strip()
                    git(repo, 'update-index', '--add', '--cacheinfo', '100644', blob, name, env=env)
            tree = git(repo, 'write-tree', env=env).stdout.decode().strip()
            old_tree = git(repo, 'rev-parse', parent + '^{tree}').stdout.decode().strip()
            if tree == old_tree:
                print('NO GITHUB CHANGES')
                return parent
            commit = git(repo, 'commit-tree', tree, '-p', parent, '-m',
                         'Latest Jubilee camera burst - ' + captured.isoformat()).stdout.decode().strip()
            if before_push:
                before_push(attempt)
            pushed = git(repo, 'push', '--quiet', 'origin', commit + ':refs/heads/main', check=False)
            if pushed.returncode == 0:
                print('GITHUB APPEND-ONLY PUBLISH SUCCESS: ' + commit)
                return commit
            if attempt + 1 < attempts:
                time.sleep(1)
    raise RuntimeError('Publication failed after bounded retries; no force push attempted')

if __name__ == '__main__':
    try:
        publish()
    except Exception as exc:
        print('Publication refused: ' + str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Publication failed: ' + type(exc).__name__)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Selected research evidence only. GET existing captures; never assign labels."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.request import Request, urlopen
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(doc):
    return (json.dumps(doc, sort_keys=True, indent=2) + '\n').encode()


def aware(value):
    dt = datetime.fromisoformat(value)
    if dt.utcoffset() is None:
        raise ValueError('Offset-aware capture identity required')
    return dt


def safe_name(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe evidence path')
    return name


def get_bytes(url, token=None):
    headers = {'User-Agent': 'jubilee-research-sealer', 'Cache-Control': 'no-cache'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('Evidence object too large')
    return data


def fetch_artifact(repo, artifact_id, run_id, source_commit, token, get=get_bytes):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    url = f'https://api.github.com/repos/{repo}/actions/artifacts/{int(artifact_id)}'
    metadata = json.loads(get(url, token))
    run = metadata['workflow_run']
    if metadata['id'] != int(artifact_id) or run['id'] != int(run_id) or run['head_sha'] != source_commit:
        raise ValueError('Artifact identity mismatch')
    if metadata['expired'] or aware(metadata['expires_at']) <= datetime.now(timezone.utc):
        raise ValueError('Artifact expired')
    expected = metadata.get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', expected):
        raise ValueError('Artifact digest unavailable')
    raw = get(url + '/zip', token)
    if digest(raw) != expected[7:]:
        raise ValueError('Artifact ZIP hash mismatch')
    # Keep stable origin facts, not expiring signed URLs or authentication.
    origin = {k: metadata[k] for k in ('id', 'name', 'digest', 'created_at', 'expires_at', 'workflow_run')}
    origin['repository'] = repo
    return raw, origin


def verify_packet(raw, origin):
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError('Packet too large')
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = safe_name(entry.filename)
            if name in files:
                raise ValueError('Duplicate ZIP member')
            files[name] = archive.read(entry)
    packet = json.loads(files['packet.json'])
    if packet['source_commit'] != origin['workflow_run']['head_sha']:
        raise ValueError('Packet commit mismatch')
    if digest(raw) != origin['digest'].removeprefix('sha256:'):
        raise ValueError('ZIP hash mismatch')
    for name, expected in packet['retained_sha256'].items():
        safe_name(name)
        if digest(files[name]) != expected:
            raise ValueError('Retained file hash mismatch: ' + name)
    if set(files) != set(packet['retained_sha256']) | {'packet.json'}:
        raise ValueError('Unaccounted packet files')
    capture = aware(packet['capture_cycle_time_ct'])
    for name in ('status.json', 'burst_status.json', 'vision.json'):
        if aware(json.loads(files[name])['capture_time_ct']) != capture:
            raise ValueError('Packet capture identity mismatch')
    shots = json.loads(files['burst_status.json'])['cameras'][packet['primary_camera_id']]['shots']
    if packet['primary_shots'] != [{k: s.get(k) for k in ('timestamp_ct', 'timing', 'shot')} for s in shots]:
        raise ValueError('Packet shot identity mismatch')
    if packet['tier_a_verified'] or packet['whole_morning_outcome'] != 'UNKNOWN' or packet['biological_event_label'] != 'unknown' or packet['clean_training_negative_count'] != 0 or packet['forecast_predictor_eligible'] or packet['search_absence_is_negative'] or packet['production_action'] != 'NO_CHANGE':
        raise ValueError('Research packet guardrails violated')
    return packet, files


def retrieve_burst(packet, files, get):
    capture = aware(packet['capture_cycle_time_ct'])
    prefix = capture.strftime('archive/%Y-%m-%d/%H%M%S')
    key = prefix + '/manifest.json'
    raw = get(key)
    manifest = json.loads(raw)
    if aware(manifest['capture_time_ct']) != capture or manifest['archive_prefix'] != prefix:
        raise ValueError('R2 capture identity mismatch')
    if not manifest.get('capture_id', '').startswith(capture.strftime('%Y%m%dT%H%M%S%f') + '-'):
        raise ValueError('R2 capture ID mismatch')
    camera = packet['primary_camera_id']
    if camera != 'montrose_shoreline':
        raise ValueError('Unsupported primary camera')
    retained = {'r2/manifest.json': raw}
    # Bind the archive to the pinned metadata, not merely a guessed second key.
    local_hashes = manifest['local_capture_sha256']
    for name in ('status.json', 'burst_status.json', 'vision.json', camera + '.jpg'):
        if local_hashes[name] != digest(files[name]):
            raise ValueError('R2 local capture binding mismatch: ' + name)
    for name in ('burst_status.json', 'vision.json'):
        content = get(prefix + '/' + name)
        if digest(content) != manifest['sha256'][prefix + '/' + name] or content != files[name]:
            raise ValueError('R2 archived metadata mismatch')
        retained['r2/' + name] = content
    info = manifest['cameras'][camera]
    shots = info['burst']
    if info['ok'] is not True or len(shots) != 3 or {s['shot'] for s in shots} != {1, 2, 3}:
        raise ValueError('R2 incomplete burst')
    expected_shots = {s['shot']: s for s in packet['primary_shots']}
    source_shots = {s['shot']: s for s in json.loads(files['burst_status.json'])['cameras'][camera]['shots']}
    for shot in shots:
        number = shot['shot']
        expected = expected_shots[number]
        if aware(shot['timestamp_ct']) != aware(expected['timestamp_ct']) or shot['timing'] != expected['timing']:
            raise ValueError('R2 shot identity mismatch')
        frame_key = f'{prefix}/burst/{camera}_{number}.jpg'
        if shot['archive_key'] != frame_key:
            raise ValueError('R2 frame key mismatch')
        content = get(frame_key)
        measured = digest(content)
        if measured != manifest['sha256'][frame_key] or measured != local_hashes[f'burst_latest/{camera}_{number}.jpg']:
            raise ValueError('R2 frame hash mismatch')
        if len(content) != shot['bytes'] or len(content) != source_shots[number]['bytes']:
            raise ValueError('R2 frame size mismatch')
        if number == 3 and measured != packet['latest_image_sha256']:
            raise ValueError('R2 latest image binding mismatch')
        retained[f'r2/burst/{camera}_{number}.jpg'] = content
    if get(key) != raw:
        raise ValueError('R2 manifest changed during readback')
    return retained, manifest['capture_id'], key


def readback(directory):
    """Reopen everything. Any missing/corrupt receipt or payload is a gap."""
    directory = Path(directory)
    try:
        receipt_raw = (directory / 'receipt.json').read_bytes()
        if digest(receipt_raw) != directory.name:
            raise ValueError('Receipt identity mismatch')
        receipt = json.loads(receipt_raw)
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(receipt['sealed_sha256']) | {'receipt.json'}:
            raise ValueError('Sealed file inventory mismatch')
        for name, expected in receipt['sealed_sha256'].items():
            if digest((directory / safe_name(name)).read_bytes()) != expected:
                raise ValueError('Sealed file hash mismatch')
        if 'source-artifact.zip' in receipt['sealed_sha256']:
            verify_packet((directory / 'source-artifact.zip').read_bytes(), receipt['origin'])
        return {'readback_status': 'VERIFIED', 'evidence_status': receipt['evidence_status'],
                'tier_a_verified': False, 'whole_morning_outcome': 'UNKNOWN'}
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        return {'readback_status': 'EVIDENCE_GAP', 'gap': type(exc).__name__,
                'tier_a_verified': False, 'whole_morning_outcome': 'UNKNOWN'}


def seal(archive_root, raw, origin, get, source_gap=None):
    """Content-addressed create-only receipt; original packet bytes are unchanged."""
    files, packet, gaps = {}, None, []
    if source_gap:
        gaps.append(source_gap)
    else:
        packet, packet_files = verify_packet(raw, origin)
        files['source-artifact.zip'] = raw
        files.update({'packet/' + n: b for n, b in packet_files.items()})
    capture_id = None
    key = None
    if packet:
        try:
            burst_files, capture_id, key = retrieve_burst(packet, packet_files, get)
            files.update(burst_files)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Do not persist a partial burst as a verified complete archive.
            gaps.append('R2_READBACK_' + type(exc).__name__)
    receipt = {'schema_version': '1.0', 'origin': origin,
               'packet_sha256': digest(packet_files['packet.json']) if packet else None,
               'capture_cycle_time_ct': packet['capture_cycle_time_ct'] if packet else None,
               'capture_id': capture_id, 'manifest_key': key,
               'evidence_status': 'VERIFIED_THREE_FRAME_RETENTION' if packet and not gaps else 'EVIDENCE_GAP',
               'gaps': gaps, 'sealed_at_utc': datetime.now(timezone.utc).isoformat(),
               'sealed_sha256': {n: digest(b) for n, b in files.items()},
               'sample_classification': packet['sample_classification'] if packet else None,
               'tier_a_verified': False, 'whole_morning_outcome': 'UNKNOWN',
               'clean_training_negative_count': 0, 'production_action': 'NO_CHANGE'}
    receipt_raw = encoded(receipt)
    root = Path(archive_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / (receipt['packet_sha256'] or 'source-gaps') / digest(receipt_raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.seal-', dir=root))
    try:
        for name, content in {**files, 'receipt.json': receipt_raw}.items():
            path = stage / safe_name(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(content)
        # rename is create-only: the receipt path is never overwritten.
        if target.exists():
            raise ValueError('Seal already exists')
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    result = readback(target)
    if result['readback_status'] != 'VERIFIED':
        raise ValueError('Durable local readback failed')
    return target, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='bentsmith4/jubilee-camera-feed')
    parser.add_argument('--artifact-id', type=int, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--r2-public-base', required=True)
    parser.add_argument('--archive-root', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        parser.error('A full source commit is required')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9/_-]*)?', args.r2_public_base):
        parser.error('An HTTPS public archive base without query credentials is required')
    origin = {'repository': args.repo, 'id': args.artifact_id,
              'workflow_run': {'id': args.run_id, 'head_sha': args.source_commit}}
    gap = None
    raw = None
    try:
        raw, origin = fetch_artifact(args.repo, args.artifact_id, args.run_id,
                                     args.source_commit, os.environ.get('GH_TOKEN'))
        verify_packet(raw, origin)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        gap = 'ARTIFACT_READBACK_' + type(exc).__name__
    target, receipt = seal(args.archive_root, raw, origin,
                           lambda key: get_bytes(args.r2_public_base.rstrip('/') + '/' + key), gap)
    print(json.dumps({'path': str(target), 'evidence_status': receipt['evidence_status'],
                      'gaps': receipt['gaps'], **readback(target)}))


if __name__ == '__main__':
    main()

"""J04 preparatory migration primitives; not connected to live publication.

Inventory reads exact Git blobs, never a dirty checkout. Mirror copies original
compressed bytes, conditionally creates keys, and verifies every full GET.
No delete operation, credentials, camera paths, or automatic cutover.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ARCHIVE = 'model_data/public_archive/'
CLASSES = frozenset(('asos', 'coops', 'usgs', 'ndbc', 'wqp', 'ngofs2_subset',
                     'ngofs2_named_station_subset', 'ngofs2_shoreline_grid_subset',
                     'griidc_main_pass_20160419'))
PREFIX = 'environmental/v1/'
MAX_COMPRESSED = 64 * 1024 * 1024
MAX_RAW = 512 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def raw_bytes(data):
    require(len(data) <= MAX_COMPRESSED, 'compressed object exceeds bounded reader')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read(MAX_RAW + 1)
    require(len(raw) <= MAX_RAW, 'expanded object exceeds bounded reader')
    return raw


def identity(path, data):
    p = PurePosixPath(path)
    require(path == p.as_posix() and path.startswith(ARCHIVE)
            and len(p.parts) == 4 and p.parts[2] in CLASSES
            and '..' not in p.parts and '\\' not in path, 'invalid archive path')
    match = re.fullmatch(r'(?:[A-Za-z0-9_-]+-)?([0-9a-f]{64})\.(json|csv|txt)\.gz', p.name)
    require(match is not None, 'invalid content-addressed archive filename')
    raw = raw_bytes(data)
    require(sha(raw) == match[1], 'historical raw hash mismatch: ' + path)
    compressed = sha(data)
    return dict(path=path, raw_sha256=match[1], compressed_sha256=compressed,
                raw_bytes=len(raw), compressed_bytes=len(data),
                object_key=f'{PREFIX}objects/{p.parts[2]}/{match[1]}/{compressed}.gz')


def verify(entry, data):
    expected = identity(entry['path'], data)
    require(all(entry.get(k) == v for k, v in expected.items()), 'object identity mismatch')
    return data


def inventory(root, ref='HEAD'):
    commit = git(root, 'rev-parse', '--verify', ref + '^{commit}').decode().strip()
    tree = git(root, 'ls-tree', '-rz', commit, '--', ARCHIVE)
    entries = []
    for item in tree.split(b'\0'):
        if not item:
            continue
        meta, path = item.split(b'\t', 1)
        mode, kind, blob = meta.decode().split()
        require(mode == '100644' and kind == 'blob', 'archive is not a regular Git file')
        data = git(root, 'cat-file', 'blob', blob)
        entries.append(dict(identity(path.decode(), data), git_blob=blob))
    require(bool(entries), 'empty inventory')
    entries.sort(key=lambda e: e['path'])
    return dict(schema_version=1, scope='exact_git_tree_not_all_historical_versions',
                source_commit=commit, objects=entries)


def validate_catalog(catalog):
    require(catalog.get('schema_version') == 1, 'unsupported inventory schema')
    require(re.fullmatch('[0-9a-f]{40}', catalog.get('source_commit', '')), 'invalid source commit')
    entries = catalog.get('objects', [])
    require(bool(entries), 'empty inventory')
    require(len({e['path'] for e in entries}) == len(entries), 'duplicate logical path')
    for e in entries:
        require(re.fullmatch('[0-9a-f]{40}', e.get('git_blob', '')), 'invalid Git blob')
        require(0 < e.get('compressed_bytes', 0) <= MAX_COMPRESSED, 'invalid object size')
        path = PurePosixPath(e['path'])
        require(e['path'] == path.as_posix() and len(path.parts) == 4
                and e['path'].startswith(ARCHIVE) and path.parts[2] in CLASSES
                and '..' not in path.parts and '\\' not in e['path'], 'invalid archive path')
        for field in ('raw_sha256', 'compressed_sha256'):
            require(re.fullmatch('[0-9a-f]{64}', e.get(field, '')), 'invalid digest')
        require(e['object_key'] == f"{PREFIX}objects/{path.parts[2]}/{e['raw_sha256']}/{e['compressed_sha256']}.gz",
                'invalid immutable object key')
    return entries


def audit_manifest_references(root, catalog):
    """Check current root-level manifests at the inventory's exact Git commit."""
    entries = {e['path']: e for e in validate_catalog(catalog)}
    commit = catalog['source_commit']
    paths = git(root, 'ls-tree', '-rz', commit, '--', 'model_data/').split(b'\0')
    references = []

    def visit(value, manifest, location='$'):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    path = item.replace('\\', '/')
                    if path.startswith('public_archive/') and path.endswith('.gz'):
                        entry = entries.get('model_data/' + path)
                        require(entry is not None, 'manifest archive absent from inventory')
                        hashes = [value.get(k) for k in ('raw_sha256', 'sha256', 'subset_sha256', 'raw_subset_sha256')]
                        require(entry['raw_sha256'] in hashes, 'manifest hash mismatch')
                        references.append(dict(manifest=manifest, field=location+'.'+key, archive=path))
                visit(item, manifest, location+'.'+key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, manifest, location+f'[{index}]')

    for item in paths:
        if not item:
            continue
        meta, path = item.split(b'\t', 1)
        path = path.decode()
        if len(PurePosixPath(path).parts) == 2 and path.endswith('manifest.json'):
            visit(json.loads(git(root, 'cat-file', 'blob', meta.decode().split()[2])), path)
    return references


def get_verified(client, bucket, entry):
    body = client.get_object(Bucket=bucket, Key=entry['object_key'])['Body']
    try:
        data = body.read(entry['compressed_bytes'] + 1)
    finally:
        body.close()
    return verify(entry, data)


def missing(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404')


def mirror(root, catalog, client, bucket):
    """Resumable copy. AccessDenied/timeouts/corruption never mean 'absent'."""
    entries = validate_catalog(catalog)
    # Preflight every source against the pinned tree before making any writes.
    tree = {x['path']: x for x in inventory(root, catalog['source_commit'])['objects']}
    require(entries == [tree[k] for k in sorted(tree)], 'inventory differs from pinned Git tree')
    for entry in entries:
        data = git(root, 'cat-file', 'blob', entry['git_blob'])
        verify(entry, data)
        try:
            get_verified(client, bucket, entry)
        except Exception as exc:
            if not missing(exc):
                raise
            try:
                client.put_object(Bucket=bucket, Key=entry['object_key'], Body=data,
                                  ContentType='application/gzip', IfNoneMatch='*')
            except Exception as put_error:
                code = getattr(put_error, 'response', {}).get('Error', {}).get('Code')
                if code not in ('PreconditionFailed', '412'):
                    raise
            # Includes the race-loser path. A conflicting object is never replaced.
            get_verified(client, bucket, entry)
    return dict(schema_version=1, status='ALL_OBJECTS_GET_VERIFIED',
                verified_at_utc=datetime.now(timezone.utc).isoformat(),
                inventory_sha256=sha(encoded(catalog)), source_commit=catalog['source_commit'],
                object_count=len(entries), compressed_bytes=sum(e['compressed_bytes'] for e in entries),
                bucket=bucket, production_cutover=False, deletion_performed=False)


def restore(catalog, client, bucket, destination):
    """Restore to a NEW directory. Never overwrite the repository or an old restore."""
    entries = validate_catalog(catalog)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for entry in entries:
        # Validate identity before constructing a filesystem destination.
        data = get_verified(client, bucket, entry)
        target = destination / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    return dict(status='ALL_OBJECTS_RESTORED', object_count=len(entries),
                inventory_sha256=sha(encoded(catalog)), production_cutover=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='action', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('--ref', default='HEAD')
    inv.add_argument('--out', type=Path, required=True)
    for action in ('mirror', 'restore'):
        p = sub.add_parser(action)
        p.add_argument('--inventory', type=Path, required=True)
        p.add_argument('--inventory-sha256', required=True)
        p.add_argument('--bucket', required=True)
        p.add_argument('--endpoint', required=True)
        p.add_argument('--receipt', type=Path, required=True)
        if action == 'mirror':
            p.add_argument('--confirm-environmental-bucket', required=True)
        else:
            p.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'inventory':
        result = inventory(args.root, args.ref)
        with args.out.open('xb') as stream:
            stream.write(encoded(result))
        print(json.dumps(dict(objects=len(result['objects']), inventory_sha256=sha(encoded(result)),
                              compressed_bytes=sum(e['compressed_bytes'] for e in result['objects']))))
        return
    # Deliberately no fallback to desktop camera credentials/configuration.
    import os
    import boto3
    from botocore.config import Config
    from urllib.parse import urlsplit
    url = urlsplit(args.endpoint)
    require(url.scheme == 'https' and url.hostname and not url.username and not url.password
            and not url.query and not url.fragment and url.path in ('', '/'), 'invalid S3 HTTPS endpoint')
    require(args.bucket != 'jubilee-cameras', 'camera bucket is excluded')
    if args.action == 'mirror':
        require(args.confirm_environmental_bucket == args.bucket, 'explicit environmental destination required')
    payload = args.inventory.read_bytes()
    require(sha(payload) == args.inventory_sha256, 'inventory file hash mismatch')
    catalog = json.loads(payload)
    require(payload == encoded(catalog), 'inventory must use canonical encoding')
    require(not args.receipt.exists(), 'receipt already exists')
    client = boto3.client('s3', endpoint_url=args.endpoint, region_name='auto',
                          aws_access_key_id=os.environ['JUBILEE_ENV_ACCESS_KEY_ID'],
                          aws_secret_access_key=os.environ['JUBILEE_ENV_SECRET_ACCESS_KEY'],
                          config=Config(connect_timeout=10, read_timeout=60, retries={'max_attempts':3}))
    if args.action == 'mirror':
        result = mirror(args.root, catalog, client, args.bucket)
    else:
        result = restore(catalog, client, args.bucket, args.destination)
    with args.receipt.open('xb') as stream:
        stream.write(encoded(result))
    print(result['status'])


if __name__ == '__main__':
    main()

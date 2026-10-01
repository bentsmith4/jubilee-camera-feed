"""Explicit full offline replay. Requires the external 95 MB source archive.

Verifies the supplied archive against the acquired ZIP hash and all 68 member
hashes. This does not resolve its mismatch with the provider's original ZIP.
No network access, model imports, production writes or accepted current labels.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def file_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_archive(archive, manifest):
    require(archive.stat().st_size == manifest['archive']['bytes'], 'archive_size_mismatch')
    require(file_sha256(archive) == manifest['archive']['sha256'], 'acquired_archive_hash_mismatch')
    expected = {r['path']: r for r in manifest['raw_members']}
    with zipfile.ZipFile(archive) as source:
        require(len(source.namelist()) == len(expected), 'archive_member_count_mismatch')
        require(set(source.namelist()) == set(expected), 'archive_member_names_mismatch')
        require(source.testzip() is None, 'archive_crc_failure')
        for member in source.infolist():
            row = expected[member.filename]
            require(member.file_size == row['bytes'], 'archive_member_size_mismatch')
            require(hashlib.sha256(source.read(member.filename)).hexdigest() == row['sha256'],
                    'archive_member_hash_mismatch')


def verify_all_velocity_rows(path, expected_count, available_at):
    """Check every row; counts alone cannot establish unchanged production gates."""
    required = {
        'earth_east_mps': '', 'earth_north_mps': '',
        'validated_current': 'False', 'production_weight': '0',
        'coordinate_system': 'SHIP', 'available_at_utc': available_at,
        'velocity_frame': 'WATER_RELATIVE_TO_INSTRUMENT',
        'bottom_difference_status': 'RESEARCH_DIAGNOSTIC_NOT_VALIDATED',
    }
    count = 0
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for count, row in enumerate(csv.DictReader(stream), 1):
            for field, value in required.items():
                require(row.get(field) == value, f'production_gate_violation_row_{count}_{field}')
    require(count == expected_count, 'velocity_row_count_mismatch')
    return count


def full_replay(archive, out, require_reference_hashes=False):
    manifest = json.loads((ROOT / 'provenance.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['supporting_file_sha256'].items():
        require(file_sha256(ROOT / relative) == expected, f'supporting_file_hash_mismatch_{relative}')
    verify_archive(archive, manifest)
    acquired = dt.datetime.fromtimestamp(archive.stat().st_mtime, dt.timezone.utc).isoformat()
    reference_clock_matches = acquired == manifest['reference_ingested_at_utc']
    require(not require_reference_hashes or reference_clock_matches,
            'reference_replay_requires_original_archive_modification_time; do_not_relabel_a_new_acquisition')
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())), 'output_directory_must_be_empty')
    out.mkdir(parents=True, exist_ok=True)
    # The decoder reads only station.target_lat/target_lon. Use the immutable
    # reference snapshot rather than whichever live nowcast the checkout has.
    with tempfile.TemporaryDirectory(prefix='adcp-reference-') as folder:
        reference = Path(folder)
        (reference / 'model_data').mkdir()
        shutil.copyfile(ROOT / 'point_clear_reference_source.json',
                        reference / 'model_data/ngofs2_point_clear_nowcast_manifest.json')
        subprocess.run([sys.executable, str(ROOT / 'ingest_ship_channel.py'),
                        '--archive', str(archive), '--listing-dir', str(ROOT / 'provider_metadata'),
                        '--repo', str(reference), '--out', str(out)], check=True)
    subprocess.run([sys.executable, str(ROOT / 'motion_consistency.py'),
                    '--results-dir', str(out)], check=True)
    summary = json.loads((out / 'ingestion_summary.json').read_text(encoding='utf-8'))
    require(summary['counts'] == manifest['reference_counts'], 'decoded_counts_mismatch')
    require(summary['raw_files'] == manifest['raw_members'], 'decoded_member_manifest_mismatch')
    require(summary['production_weight'] == 0 and summary['production_action'] == 'NO_CHANGE',
            'summary_production_gate_violation')
    count = verify_all_velocity_rows(out / 'velocity_bins.csv.gz',
                                    manifest['reference_counts']['velocity_bin_rows'],
                                    manifest['available_at_utc'])
    env = os.environ.copy()
    env.update(ADCP_ARCHIVE=str(archive), ADCP_RESULTS=str(out))
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                             '-s', str(ROOT / 'archive_tests'), '-p', 'test_*.py', '-v'],
                            env=env, capture_output=True, text=True)
    (out / 'archive-tests.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    require(result.returncode == 0, 'archive_tests_failed; see archive-tests.txt')
    actual = {name: file_sha256(out / name) for name in manifest['reference_result_sha256']}
    matches = {name: value == manifest['reference_result_sha256'][name] for name, value in actual.items()}
    # Acquisition timestamps affect four output files. They may differ after
    # a later download, but byte-identical replay is mandatory for this clock.
    if reference_clock_matches:
        require(all(matches.values()), 'reference_output_hash_mismatch')
    for name in ['motion_consistency.json', 'motion_pairs.csv']:
        require(matches[name], f'motion_output_hash_mismatch_{name}')
    receipt = {
        'status': 'PASS_RESEARCH_ONLY', 'archive_sha256': manifest['archive']['sha256'],
        'provider_original_archive_checksum_verified': False,
        'raw_member_hashes_verified': len(manifest['raw_members']),
        'ingested_at_utc': acquired, 'reference_clock_matches': reference_clock_matches,
        'all_velocity_rows_checked': count, 'archive_tests_passed': 8,
        'result_sha256': actual, 'reference_result_hash_matches': matches,
        'production_action': 'NO_CHANGE', 'production_weight': 0,
        'scientific_acceptance': 'NOT_ESTABLISHED',
    }
    (out / 'validation_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New or empty output directory outside the repository')
    parser.add_argument('--require-reference-hashes', action='store_true',
                        help='Require original acquisition timestamp and all six reference output hashes')
    args = parser.parse_args()
    full_replay(args.archive.resolve(), args.out.resolve(), args.require_reference_hashes)

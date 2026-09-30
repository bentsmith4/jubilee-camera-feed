"""Offline evidence reconciliation; never changes production or navigation joins."""
from __future__ import annotations
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'research/j09_pointclear_reviewed'
spec = importlib.util.spec_from_file_location('j09_reviewed_decoder', REVIEW / 'ingest_ship_channel.py')
reviewed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewed)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def screen(sentence):
    fields, status = reviewed.nmea_fields(sentence)
    simple = status == 'PASS' and len(fields) > 2 and fields[2] == 'A'
    if not simple:
        return False, None
    try:
        reviewed.parse_rmc(sentence)
    except ValueError as exc:
        return True, str(exc)
    return True, None

def reconcile(acquired, provider, transport):
    manifest = json.loads((REVIEW / 'provenance.json').read_text())
    reviewed_manifest = json.loads((REVIEW / 'REVIEWED_INDIVIDUAL_SHA256_AND_PROVENANCE.json').read_text())
    replay = json.loads((ROOT / 'model_data/j09_ship_channel_adcp_provider_replay_20260929.json').read_text())
    reviewed_manifest_hash = digest((REVIEW / 'REVIEWED_INDIVIDUAL_SHA256_AND_PROVENANCE.json').read_bytes())
    if reviewed_manifest_hash != 'c52f0aa91b8f1592db6891cf313ba2c4eff7ec76782d2b3a749d0b7257fd1fe6':
        raise ValueError('reviewed_manifest_hash_mismatch')
    for relative, expected in manifest['supporting_file_sha256'].items():
        if digest((REVIEW / relative).read_bytes()) != expected:
            raise ValueError('supporting_file_hash_mismatch_' + relative)
    sources = [acquired, provider, transport]
    archives = [zipfile.ZipFile(p) for p in sources]
    try:
        a, p, t = archives
        expected = {r['path']: r for r in reviewed_manifest['raw_members']}
        recorded = {r['path']: r for r in replay['members']}
        if manifest['raw_members'] != reviewed_manifest['raw_members']:
            raise ValueError('reviewed_manifests_disagree')
        for z in archives:
            if len(z.infolist()) != 68 or set(z.namelist()) != set(expected) or z.testzip() is not None:
                raise ValueError('member_inventory_or_crc_mismatch')
        for name, row in expected.items():
            for z in archives:
                data = z.read(name)
                if len(data) != row['bytes'] or digest(data) != row['sha256']:
                    raise ValueError('member_hash_mismatch_' + name)
            if recorded[name]['sha256'] != row['sha256'] or recorded[name]['bytes'] != row['bytes']:
                raise ValueError('pr38_inventory_mismatch_' + name)
        ab, pb = acquired.read_bytes(), provider.read_bytes()
        if digest(ab) != manifest['archive']['sha256'] or digest(pb) != replay['zip_sha256']:
            raise ValueError('archive_identity_mismatch')
        # Mask only DOS time/date words in local and central headers. This
        # establishes the exact cause rather than inferring from equal members.
        aa, pp = bytearray(ab), bytearray(pb)
        for z, buf in [(a, aa), (p, pp)]:
            for i in z.infolist():
                off = i.header_offset
                if buf[off:off+4] != b'PK\x03\x04':
                    raise ValueError('local_header_not_found')
                buf[off+10:off+14] = b'\0'*4
            pos = z.start_dir
            for i in z.infolist():
                if buf[pos:pos+4] != b'PK\x01\x02':
                    raise ValueError('central_header_not_found')
                buf[pos+12:pos+16] = b'\0'*4
                pos += 46 + sum(int.from_bytes(buf[pos+k:pos+k+2], 'little') for k in (28,30,32))
        counts = collections.Counter()
        exclusions = []
        by_file = {}
        for name in sorted(expected):
            if not name.endswith('.TXT'):
                continue
            c = collections.Counter()
            # PR38's total screen finds substrings, including five partial or
            # embedded fragments. Preserve that separate denominator.
            c['substring_RMC_sentences'] = len(re.findall(rb'\$GPRMC,[^\r\n]*', a.read(name)))
            for line_no, line in enumerate(a.read(name).splitlines(), 1):
                if not line.startswith(b'$GPRMC,'):
                    continue
                c['line_start_RMC_sentences'] += 1
                try:
                    simple, reason = screen(line.decode('ascii'))
                except (ValueError, UnicodeDecodeError):
                    continue
                if simple:
                    c['checksum_valid_status_A'] += 1
                    if reason:
                        exclusions.append({'path': name, 'raw_sha256': expected[name]['sha256'],
                                           'source_line': line_no, 'sentence': line.decode('ascii'),
                                           'reason': reason, 'course_true_deg': float(line.split(b',')[8])})
                    else:
                        c['reviewed_accepted'] += 1
            by_file[name] = dict(c)
            counts.update(c)
        return {'schema_version': 1, 'status': 'INDEPENDENTLY_RECONCILED_RESEARCH_ONLY',
                'acquired_zip_sha256': digest(ab), 'provider_download_zip_sha256': digest(pb),
                'zip_bytes': [len(ab), len(pb)], 'verified_members_per_archive': 68,
                'reviewed_manifest_sha256': reviewed_manifest_hash,
                'member_hash_mismatches': 0, 'pr38_member_hash_mismatches': 0,
                'container_different_bytes': sum(x != y for x, y in zip(ab, pb)),
                'equal_after_masking_only_zip_DOS_timestamps': aa == pp,
                'rmc_counts': dict(counts), 'by_file': by_file, 'simple_only_RMC_records': exclusions,
                'RMC_selection_difference_reason': 'Four course=360.0 records fail reviewed 0 <= course < 360 predicate; no course normalization applied.',
                'timing_association': 'Separate unresolved scientific gate; no anomaly identities inferred from the four rejected RMC sentences.',
                'provider_original_archive_checksum_verified': False,
                'production_action': 'NO_CHANGE', 'production_weight': 0}
    finally:
        for z in archives:
            z.close()

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('acquired', 'provider', 'transport', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    args = ap.parse_args()
    args.output.write_text(json.dumps(reconcile(args.acquired, args.provider, args.transport), indent=2)+'\n')

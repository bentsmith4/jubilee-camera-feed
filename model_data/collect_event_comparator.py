#!/usr/bin/env python3
"""Outcome-blind research extension of the existing packet, never a label writer."""
import argparse
import json
from pathlib import Path
import subprocess

from collect_matched_control_packet import collect
from seal_matched_control_packet import digest, encoded, get_bytes, retrieve_burst

PROTOCOL = 'model_data/montrose_event_pair_protocol.json'
PUBLIC_ARCHIVE = 'https://pub-bf6207fce382460991eaf48ec8090b1a.r2.dev'


def enrich(root, out, get):
    root, out = Path(root), Path(out)
    packet_path = out / 'packet.json'
    original = packet_path.read_bytes()
    packet = json.loads(original)
    if 'event_comparator' in packet:
        raise ValueError('Never overwrite enriched evidence')
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--', PROTOCOL]):
        raise ValueError('Matching protocol differs from the capture commit')
    protocol = (root / PROTOCOL).read_bytes()
    design = json.loads(protocol)
    files = {n: (out / n).read_bytes() for n in packet['retained_sha256']}
    for n, expected in packet['retained_sha256'].items():
        if digest(files[n]) != expected:
            raise ValueError('Input packet hash mismatch')
    additions = {PROTOCOL: protocol, 'original-packet.json': original}
    gaps = []
    capture_id = None
    try:
        retained, capture_id, _ = retrieve_burst(packet, files, get)
        additions.update(retained)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        gaps.append('BURST_READBACK_' + type(exc).__name__)
    # A blank review ledger is retained at capture time, not a fabricated review.
    review = {
        'protocol_sha256': digest(protocol), 'capture_id': capture_id,
        'capture_source_commit': packet['source_commit'],
        'actual_shots': packet['primary_shots'], 'roi_id': design['roi']['id'],
        'geometry_review': 'NOT_PERFORMED', 'physical_site_binding': 'UNKNOWN',
        'subsegment_mask': None, 'landmark_registration_error_px': None,
        'pixel_review': 'NOT_PERFORMED', 'reviewer': None, 'reviewed_at': None,
        'biological_event_label': 'unknown', 'direct_biology_evidence': [],
        'event_id': None, 'episode_id': None,
        'observed_event_interval': None, 'onset': 'UNKNOWN', 'ending': 'UNKNOWN',
        'timestamp_uncertainty_seconds': None,
        'matching_evidence': {k: {'status': 'UNKNOWN', 'value': None,
                                'source': None, 'qc': None, 'available_at': None,
                                'evidence_refs': []}
                              for k in design['matching_tolerances']},
        'incidental_independent_observations': [],
        'unobserved_intervals': 'UNKNOWN', 'whole_morning_outcome': 'UNKNOWN',
        'tier_a_verified': False, 'forecast_predictor_eligible': False,
        'production_action': 'NO_CHANGE'
    }
    additions['event-review-template.json'] = encoded(review)
    # Added bytes are part of the existing sealer's authenticated hash inventory.
    for name, raw in additions.items():
        target = out / name
        if target.exists():
            raise ValueError('Evidence file already exists: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        packet['retained_sha256'][name] = digest(raw)
    packet['event_comparator'] = {
        'protocol_id': design['protocol_id'], 'protocol_sha256': digest(protocol),
        'capture_id': capture_id,
        'burst_retention': 'VERIFIED_THREE_FRAME_RETENTION' if not gaps else 'EVIDENCE_GAP',
        'gaps': gaps, 'review_ledger': 'event-review-template.json',
        'selection': 'All existing capture commits, regardless of model risk or outcome',
        'geometry_status': 'UNVALIDATED', 'event_confirmation': 'UNKNOWN',
        'pair_status': 'UNRESOLVED', 'tier_a_verified': False,
    }
    # Keep original NOT_VERIFIED pointer and original packet bytes for provenance.
    # The extension describes new GET readback only; it does not revise labels.
    packet_path.write_bytes(encoded(packet))
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    collect(args.repo, args.out)
    result = enrich(args.repo, args.out, lambda key: get_bytes(PUBLIC_ARCHIVE + '/' + key))
    print(json.dumps(result['event_comparator']))


if __name__ == '__main__':
    main()

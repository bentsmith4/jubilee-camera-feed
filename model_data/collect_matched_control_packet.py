#!/usr/bin/env python3
"""Read-only capture evidence collector. Never assigns a training label."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from build_observation_effort_snapshot import camera_integrity, in_window, parse_dt
from build_observation_effort_snapshot import no_visual_event_evidence, sufficient_contact_detectability

METADATA = ('status.json', 'burst_status.json', 'vision.json')
CONTEXT = (
    'model_data/matched_control_contract.json',
    'model_data/private_camera_signal_contracts.json',
    'model_data/public_camera_signal_contracts.json',
    'model_data/public_camera_observation_log.json',
    'model_data/event_history.json',
    'model_data/current_state_snapshot.json',
    'model_data/asos_weather_manifest.json',
    'model_data/river_forcing_manifest.json',
    'model_data/weeks_bay_realtime_manifest.json',
    'model_data/ngofs2_point_clear_nowcast_manifest.json',
    'model_data/ngofs2_mobile_bay_named_stations_nowcast_manifest.json',
)


def collect(root, out, now=None):
    root, out = root.resolve(), out.resolve()
    if out == root or root in out.parents:
        raise ValueError('Evidence output must be outside the checkout')
    if out.exists():
        raise ValueError('Use a new evidence directory; never overwrite a packet')
    now = now or datetime.now(timezone.utc)
    docs = {name: json.loads((root/name).read_text()) for name in METADATA}
    status, burst, vision = (docs[n] for n in METADATA)
    capture = parse_dt(status.get('capture_time_ct'))
    if capture is None:
        raise ValueError('Offset-aware capture identity required')
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    # Reject dirty inputs; the source SHA must identify the bytes being archived.
    files = list(METADATA) + list(CONTEXT) + ['montrose_shoreline.jpg']
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--', *files]):
        raise ValueError('Evidence inputs differ from the pinned commit')
    out.mkdir(parents=True)
    retained, missing = {}, []
    for name in files:
        source = root/name
        if not source.is_file():
            missing.append(name)
            continue
        dest = out/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        retained[name] = hashlib.sha256(dest.read_bytes()).hexdigest()
    contract_raw = (root/'model_data/matched_control_contract.json').read_bytes()
    contract_blob = hashlib.sha1(b'blob '+str(len(contract_raw)).encode()+b'\0'+contract_raw).hexdigest()
    issues, image_hash = camera_integrity('montrose_shoreline', status, burst, vision, root, now)
    v = vision.get('cameras', {}).get('montrose_shoreline', {})
    start, end = (parse_dt(status.get(k)) for k in ('window_start_ct', 'window_end_ct'))
    target = in_window(capture, start, end)
    qualified = target and not issues and sufficient_contact_detectability(v)
    classification = ('CANDIDATE_VISIBLE_SCOPE_CONTROL' if qualified and no_visual_event_evidence(v)
                      else 'UNKNOWN_OR_EVENT_REVIEW_REQUIRED')
    shots = burst.get('cameras', {}).get('montrose_shoreline', {}).get('shots', [])
    # The Git mirror contains only the latest image. R2's existing three-frame
    # archive is a discovery pointer, not verified evidence until retrieved.
    packet = {
        'schema_version': '1.0', 'source_commit': sha,
        'collected_at_utc': now.isoformat(), 'capture_cycle_time_ct': capture.isoformat(),
        'contract_blob_sha': contract_blob, 'retained_sha256': retained, 'missing_files': missing,
        'primary_camera_id': 'montrose_shoreline',
        'visible_scope': '437 waterline/beach segments actually resolved; no whole-cell extrapolation',
        'primary_shots': [{'timestamp_ct': s.get('timestamp_ct'), 'timing': s.get('timing'),
                           'shot': s.get('shot')} for s in shots],
        'latest_image_sha256': image_hash, 'integrity_issues': issues,
        'visibility': v.get('visibility', 'unknown'), 'detectability': v.get('detectability', 'unknown'),
        'target_window_start_ct': status.get('window_start_ct'),
        'target_window_end_ct': status.get('window_end_ct'),
        'cycle_in_target_window': target, 'sample_classification': classification,
        'biological_event_label': 'unknown',
        'existing_burst_archive': {
            'manifest_key_candidate': capture.strftime('archive/%Y-%m-%d/%H%M%S/manifest.json'),
            'readback_status': 'NOT_VERIFIED', 'all_three_frames_retained_in_packet': False,
        },
        'matching_dimensions': {k: {'status': 'UNRESOLVED', 'matched_event_id': None}
                                for k in json.loads(contract_raw)['matching_dimensions']},
        'context_interpretation': 'Checkout-time context only; validate source timestamps, QC, geometry and available_at before pairing. Not automatically capture-time observations.',
        'unobserved_intervals': 'All intervals between sampled frames and bursts remain UNKNOWN.',
        'whole_morning_outcome': 'UNKNOWN', 'search_absence_is_negative': False,
        'independent_pixel_review': 'NOT_PERFORMED', 'tier_a_verified': False,
        'clean_training_negative_count': 0, 'forecast_predictor_eligible': False,
        'production_action': 'NO_CHANGE',
    }
    (out/'packet.json').write_text(json.dumps(packet, indent=2)+'\n')
    return packet


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.repo, args.out)
    print(json.dumps({k: result[k] for k in ('source_commit', 'sample_classification', 'tier_a_verified')}))

#!/usr/bin/env python3
"""Audit upstream camera evidence without changing forecasts or starting cameras."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HUMAN_FIELDS = ('people_present', 'flashlight_activity', 'motion_pattern',
                'clustered_search_behavior', 'temporal_persistence', 'human_sensor_score')

def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None

def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}

def safe_file(root, name):
    p = (root / name).resolve()
    return p if p.is_relative_to(root.resolve()) else None

def audit(registry, status, burst, vision, root, now):
    capture_times = [timestamp(x.get('capture_time_ct')) for x in (status, burst, vision)]
    aligned = all(capture_times) and len(set(capture_times)) == 1
    output = []
    for camera in registry['cameras']:
        if camera['access'] != 'owner_google':
            continue
        cid = camera['camera_id']
        s = status.get('cameras', {}).get(cid, {})
        b = burst.get('cameras', {}).get(cid, {})
        v = vision.get('cameras', {}).get(cid, {})
        issues = []
        if not s:
            issues.append('MISSING_EXPECTED_CAMERA')
        elif not s.get('ok'):
            issues.append('CAPTURE_FAILED')
        t = timestamp(s.get('timestamp_ct'))
        age = (now - t).total_seconds() if t else None
        if age is None:
            issues.append('MISSING_OFFSET_AWARE_TIMESTAMP')
        elif age < -5:
            issues.append('FUTURE_TIMESTAMP')
        elif age > 3600:
            issues.append('STALE')
        if not aligned:
            issues.append('CAPTURE_BURST_VISION_MISMATCH')
        shots = b.get('shots', [])
        times = [timestamp(x.get('timestamp_ct')) for x in shots]
        temporal_ok = (b.get('ok') is True and len(times) == 3 and all(times)
                       and all(5 <= (times[i + 1] - times[i]).total_seconds() <= 30 for i in (0, 1))
                       and t == times[-1])
        if not temporal_ok:
            issues.append('INVALID_OR_MISSING_TEMPORAL_BURST')
        if v.get('status') != 'ok':
            issues.append('VISION_UNAVAILABLE')
        image = root / (cid + '.jpg')
        byte_match = image.is_file() and s.get('bytes') == image.stat().st_size
        if not byte_match:
            issues.append('LATEST_IMAGE_MISSING_OR_SIZE_MISMATCH')
        raw_available = bool(shots) and all(
            (p := safe_file(root, str(x.get('file', '')))) is not None and p.is_file()
            and p.stat().st_size == x.get('bytes') for x in shots)
        missing_human = [field for field in HUMAN_FIELDS if field not in v]
        output.append({
            'camera_id': cid, 'site_group': camera['site_group'],
            'shoreline_cell': camera['shoreline_cell'],
            'configuration_state': camera['configuration_state'],
            'captured_at_utc': t.isoformat() if t else None,
            'age_minutes': round(age / 60, 2) if age is not None else None,
            'upstream_metadata_pass': not issues,
            'issues': issues, 'raw_three_frame_pixels_in_mirror': raw_available,
            'raw_archive_verification': 'mirror_available' if raw_available else 'NOT_VERIFIED',
            'missing_human_sensor_fields': missing_human,
            'latest_image_sha256': hashlib.sha256(image.read_bytes()).hexdigest() if byte_match else None,
            'negative_event_label_allowed': False,
        })
    passing = [x for x in output if x['upstream_metadata_pass']]
    return {
        'schema_version': '2.0', 'generated_at_utc': now.isoformat(),
        'audit_type': 'metadata_and_latest_file_integrity_not_independent_vision',
        'status': 'pass' if len(passing) == len(output) else 'degraded',
        'expected_private_cameras': len(output), 'private_metadata_pass': len(passing),
        'passing_site_groups': sorted({x['site_group'] for x in passing}),
        'private_cameras': output,
        'unknown_upstream_camera_ids': sorted(set(status.get('cameras', {})) - {x['camera_id'] for x in output}),
        'public_capture_contract': 'separate_snapshot_probe_not_a_temporal_burst',
        'forecast_changed': False,
        'caveat': 'No detection is not an observed non-event; missing cameras remain explicitly visible.',
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = audit(load(a.root / 'model_data/camera_sources.json'),
                   load(a.root / 'status.json'), load(a.root / 'burst_status.json'),
                   load(a.root / 'vision.json'), a.root, datetime.now(timezone.utc))
    dest = a.out or a.root / 'model_data/sensing_audit.json'
    dest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'expected_private_cameras', 'private_metadata_pass', 'passing_site_groups')}))

if __name__ == '__main__':
    main()

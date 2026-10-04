#!/usr/bin/env python3
"""Read-only sampled-effort audit; never establishes an interval non-event."""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Chicago')
# Modern screening bounds, NOT precise historical start/end times.
WINDOWS = [('late_afternoon_screen', 15, 20),
           ('1730_to_midnight', 17.5, 24),
           ('1930_to_next_0300', 19.5, 27),
           ('next_day_continuation_screen', 27, 36)]
CAMERAS = ('montrose_shoreline', 'montrose_pier_boat', 'montrose_pier_bird',
           'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth')


def parse(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.utcoffset() is None:
        raise ValueError('Offset-aware capture identity required')
    return dt.astimezone(timezone.utc)


def audit(records, day, as_of):
    cutoff = parse(as_of)
    unique = {}
    for row in records:
        t = parse(row['generated_from_capture_time_ct'])
        if t in unique and unique[t] != row:
            raise ValueError('Conflicting records for one capture identity')
        unique[t] = row
    base = datetime.combine(date.fromisoformat(day), time(), TZ)
    result = {'schema_version': '1.0', 'date_ct': day, 'as_of': as_of,
              'production_action': 'NO_CHANGE', 'clean_training_negative_count': 0,
              'whole_day_outcome': 'UNKNOWN', 'windows': [],
              'interpretation': 'Upstream sampled effort only; no independent media readback. All between-sample intervals remain UNKNOWN.'}
    for name, lo, hi in WINDOWS:
        start, end = (base + timedelta(hours=h) for h in (lo, hi))
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        observed_end = min(end, cutoff)
        rows = [(t, r) for t, r in sorted(unique.items()) if start <= t < end and t <= cutoff]
        out = {'window': name, 'start_ct': start.astimezone(TZ).isoformat(),
               'end_ct': end.astimezone(TZ).isoformat(), 'window_elapsed': cutoff >= end,
               'retained_effort_records': len(rows), 'window_outcome': 'UNKNOWN', 'cameras': []}
        for camera in CAMERAS:
            valid = []
            for t, r in rows:
                for cell in r.get('cells', []):
                    for c in cell.get('camera_rows', []):
                        if (c.get('camera_id') == camera and c.get('capture_ok') is True
                            and c.get('integrity_issues') == []
                            and c.get('visibility') in ('good', 'fair')
                            and c.get('detectability') in ('high', 'moderate')):
                            valid.append(t)
            points = [start] + sorted(set(valid)) + [observed_end]
            gap = max(((b-a).total_seconds()/60 for a,b in zip(points, points[1:])), default=0) if observed_end > start else None
            out['cameras'].append({'camera_id': camera, 'usable_effort_samples': len(set(valid)),
                                   'maximum_unsampled_elapsed_gap_minutes': gap,
                                   'media_readback': 'UNKNOWN', 'interval_outcome': 'UNKNOWN'})
        result['windows'].append(out)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--records', type=Path, default=Path('model_data/observation_records'))
    p.add_argument('--date', required=True)
    p.add_argument('--as-of', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    files = sorted(args.records.glob('*.json'))
    result = audit([json.loads(f.read_text()) for f in files], args.date, args.as_of)
    result['input_manifest_sha256'] = hashlib.sha256(json.dumps(
        [(f.name, hashlib.sha256(f.read_bytes()).hexdigest()) for f in files],
        separators=(',', ':')).encode()).hexdigest()
    result['input_record_count'] = len(files)
    # Exclusive create prevents replacing an earlier research receipt.
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()

"""Offline J10/J18 sensitivity only; no runtime imports, calls or production writes.

Provider receipt time is NOT Jubilee first-availability. Results are retrospective
proxy sensitivities; operational replay and actual savings remain unvalidated.
"""
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingest_asos_weather import normalize, observation_time, utc

CAMERA_USD = 0.01182465  # October 15 J18 post-change conditional average
TOTAL_USD = 0.01258312
CANDIDATES = [(10, 'any'), (15, 'north'), (20, 'north'),
              (15, 'northeast'), (15, 'other')]


def sector(degrees):
    d = degrees % 360
    return 'north' if d >= 315 or d < 45 else 'northeast' if d < 90 else 'other'


def usable(camera):
    return (camera.get('capture_ok') is True and camera.get('integrity_issues') == []
            and camera.get('visibility') in ('good', 'fair')
            and camera.get('detectability') in ('moderate', 'high'))


def load_weather(files):
    unique = {}
    for path in files:
        for r in json.loads(gzip.decompress(path.read_bytes())):
            if r.get('icaoId') not in ('KBFM', 'KMOB', 'KCQF'):
                continue
            unique[json.dumps(r, sort_keys=True)] = r
    series = {s: [] for s in ('KBFM', 'KMOB', 'KCQF')}
    rejected = 0
    for raw in unique.values():
        received, observed = utc(raw.get('receiptTime')), observation_time(raw)
        if not received or not observed or received < observed:
            rejected += 1
            continue
        rows, _ = normalize([raw], received)
        fields = {r['parameter']: r for r in rows}
        wind = [fields.get(k, {}) for k in ('wind_speed', 'wind_direction')]
        valid = all(r.get('value_status') == 'KNOWN' for r in wind)
        series[raw['icaoId']].append(dict(received=received, observed=observed,
            speed=wind[0].get('value') if valid else None,
            direction=wind[1].get('value') if valid else None,
            fingerprint=hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()))
    return series, len(unique), rejected


def state_at(rows, t):
    known = [r for r in rows if r['received'] <= t and r['observed'] <= t]
    if not known:
        return None
    newest = max((r['observed'], r['received']) for r in known)
    selected = [r for r in known if (r['observed'], r['received']) == newest]
    # Conflicting decoded reports are not resolved in favor of eligibility.
    if len(selected) != 1:
        return None
    r = selected[0]
    return r if t - r['observed'] <= timedelta(minutes=90) and r['speed'] is not None else None


def profile(series, t, hours, stations):
    start = t - timedelta(hours=hours)
    values = []
    for station in stations:
        rows = series[station]
        # Check both sides of all receipt and expiry transitions, not just endpoints.
        boundaries = {start, t}
        for r in rows:
            for point in (r['received'], r['observed'] + timedelta(minutes=90)):
                if start < point < t:
                    boundaries.update((point, point - timedelta(microseconds=1),
                                       point + timedelta(microseconds=1)))
        states = [state_at(rows, x) for x in boundaries]
        if any(x is None for x in states):
            return None
        values.extend(states)
    return min(x['speed'] for x in values), {sector(x['direction']) for x in values}


def qualify(p, speed, direction):
    return p is not None and p[0] >= speed and (direction == 'any' or p[1] == {direction})


def select_skips(flags, fraction):
    # Consecutive eligible runs restart after any protected/ineligible cycle.
    n = 0
    skipped = []
    for i, flag in enumerate(flags):
        if not flag:
            n = 0
            continue
        n += 1
        if int(n * fraction) > int((n - 1) * fraction):
            skipped.append(i)
    return skipped


def run(root):
    weather_files = sorted((root/'model_data/public_archive/asos').glob('*.json.gz'))
    effort_files = sorted((root/'model_data/observation_records').glob('*.json'))
    series, unique_weather, rejected = load_weather(weather_files)
    records = {}
    for path in effort_files:
        r = json.loads(path.read_text())
        t = utc(r['generated_from_capture_time_ct'])
        if t in records and records[t] != r:
            raise ValueError('Conflicting effort record at '+str(t))
        records[t] = r
    first = min(r['received'] for rows in series.values() for r in rows)
    last = max(r['received'] for rows in series.values() for r in rows)
    cycles = [(t,r) for t,r in sorted(records.items()) if first <= t <= last]
    profiles = {(hours, group): [profile(series,t,hours,stations) for t,_ in cycles]
                for hours in (1,2) for group,stations in
                [('KBFM_KMOB',('KBFM','KMOB')),('KCQF',('KCQF',))]}
    results = []
    for (hours, group), pp in profiles.items():
        for speed,direction in CANDIDATES:
            rawflags = [qualify(p,speed,direction) for p in pp]
            for protect in (False,True):
                flags = [f and (not protect or r.get('cycle_in_target_predawn_dawn_window') is False)
                         for f,(_,r) in zip(rawflags,cycles)]
                for fraction in (.25,.5,.75):
                    skipped = select_skips(flags,fraction)
                    lost_usable = lost_candidates = lost_signals = 0
                    for i in skipped:
                        r = cycles[i][1]
                        for cell in r['cells']:
                            lost_candidates += cell.get('control_eligibility') == 'CANDIDATE_VISIBLE_SCOPE_CONTROL'
                            for c in cell['camera_rows']:
                                lost_usable += usable(c)
                                lost_signals += c.get('overall_visual_signal') not in (None,'none','unknown','UNKNOWN')
                    kept = [t for i,(t,_) in enumerate(cycles) if i not in set(skipped)]
                    gaps = [(b-a).total_seconds()/60 for a,b in zip(kept,kept[1:])]
                    results.append(dict(stations=group,persistence_hours=hours,
                        minimum_sustained_knots=speed,direction=direction,protect_dawn=protect,
                        skip_fraction=fraction,eligible_cycles=sum(flags),skipped_cycles=len(skipped),
                        lost_usable_camera_samples=lost_usable,lost_scoped_candidate_cells=lost_candidates,
                        lost_nonquiet_upstream_signal_rows=lost_signals,
                        maximum_retained_capture_gap_minutes=max(gaps,default=None),
                        conditional_camera_cost_avoided_usd=round(len(skipped)*CAMERA_USD,8),
                        conditional_total_cost_fraction_avoided=len(skipped)*CAMERA_USD/(len(cycles)*TOTAL_USD),
                        skipped_capture_times=[cycles[i][0].isoformat() for i in skipped]))
    manifest=[(str(p.relative_to(root)),hashlib.sha256(p.read_bytes()).hexdigest())
              for p in weather_files+effort_files]
    return dict(schema='jubilee_wind_cadence_retrospective/v1',work_ids=['J10','J18'],
        production_action='NO_CHANGE',mode='PROVIDER_RECEIPT_PROXY_NOT_OPERATIONAL_REPLAY',
        input_manifest_sha256=hashlib.sha256(json.dumps(manifest,separators=(',',':')).encode()).hexdigest(),
        weather_archive_files=len(weather_files),unique_decoded_weather_reports=unique_weather,
        rejected_weather_timestamp_reports=rejected,effort_files=len(effort_files),
        all_unique_effort_cycles=len(records),overlap_cycles=len(cycles),
        first_weather_receipt=first.isoformat(),last_weather_receipt=last.isoformat(),
        first_overlap_capture=cycles[0][0].isoformat(),last_overlap_capture=cycles[-1][0].isoformat(),
        profile_known_counts={str(k):sum(p is not None for p in v) for k,v in profiles.items()},
        baseline_maximum_capture_gap_minutes=max((b[0]-a[0]).total_seconds()/60 for a,b in zip(cycles,cycles[1:])),
        operational_asof_eligibility='UNKNOWN_LOCAL_FIRST_AVAILABILITY_NOT_JOINED',
        actual_billing_savings=None,event_sensitivity=None,alligator_signal_losses=None,
        limitations=['Provider receipt is not local first availability; no operational eligibility claim.',
            'Observed effort denominator is not expected scheduled cycles or verified six-camera API completions.',
            'No retained positive-event camera replay; missing and between-burst intervals remain UNKNOWN.',
            'Costs use October 15 post-change average for all periods, not historical invoice or actual per-cycle costs.',
            'No current-signal veto: unseen skipped-cycle signals cannot be used to prevent the skip.',
            'Alligator fields absent from effort records; safety equivalence is unmeasured.',
            'KCQF is a separate short-history sensitivity, not a silent replacement for KBFM/KMOB.',
            'No production integration, new collection, paid analysis, scheduler, or notification.'],results=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    result=run(a.root)
    with a.out.open('x') as f:
        json.dump(result,f,indent=2); f.write('\n')

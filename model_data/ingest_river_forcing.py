#!/usr/bin/env python3
"""Fetch public upstream forcing. Never equate a dam gauge with bay arrival.

Raw response is content-addressed and compressed. All gate time series remain
separate. The downstream Coffeeville gauge is context, never extra inflow.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITES = ('02428400', '02469761', '02469762')
CFS_TO_CMS = 0.028316846592

def utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None

def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None

def normalize(document, retrieved_at, source_url):
    series = document.get('value', {}).get('timeSeries')
    if not isinstance(series, list):
        raise ValueError('Response lacks USGS timeSeries schema')
    out, seen = [], set()
    for ts in series:
        info, variable = ts.get('sourceInfo', {}), ts.get('variable', {})
        ids, codes = info.get('siteCode', []), variable.get('variableCode', [])
        if not ids or not codes:
            continue
        station, code = ids[0].get('value'), codes[0].get('value')
        if station not in SITES:
            raise ValueError('Unexpected station in response')
        unit = variable.get('unit', {}).get('unitCode', '')
        nodata = finite(variable.get('noDataValue'))
        series_id = ts.get('name', station + ':' + code)
        for group in ts.get('values', []):
            for value in group.get('value', []):
                t, numeric = utc(value.get('dateTime')), finite(value.get('value'))
                if t is None or numeric is None or numeric == nodata:
                    continue
                k = (series_id, t.isoformat(), str(value.get('value')), tuple(value.get('qualifiers', [])))
                if k in seen:
                    continue
                seen.add(k)
                qualifiers = value.get('qualifiers', [])
                out.append({'station_id': station, 'station_name': info.get('siteName'),
                            'series_id': series_id, 'parameter_code': code,
                            'parameter_name': variable.get('variableDescription'),
                            'value': numeric, 'unit': unit, 'observed_at_utc': t.isoformat(),
                            'qualifiers': '|'.join(qualifiers),
                            'research_qc_eligible': bool(qualifiers) and set(qualifiers).issubset({'A', 'P'}),
                            'retrieved_at_utc': retrieved_at.isoformat(), 'source_url': source_url,
                            'source_class': 'observed_upstream_forcing_not_bay_inflow',
                            'production_weight': 0.0})
    return out

def integrate(points, start, end, max_gap_seconds=7200):
    """Trapezoidal volume over observed segments only; no gap/edge extrapolation."""
    points = sorted(points)
    volume, seconds = 0.0, 0.0
    for (ta, qa), (tb, qb) in zip(points, points[1:]):
        gap = (tb - ta).total_seconds()
        if gap <= 0 or gap > max_gap_seconds or qa < 0 or qb < 0:
            continue
        lo, hi = max(ta, start), min(tb, end)
        if hi <= lo:
            continue
        qlo = qa + (qb - qa) * (lo - ta).total_seconds() / gap
        qhi = qa + (qb - qa) * (hi - ta).total_seconds() / gap
        dt = (hi - lo).total_seconds()
        volume += (qlo + qhi) / 2 * dt * CFS_TO_CMS
        seconds += dt
    duration = (end - start).total_seconds()
    coverage = seconds / duration if duration > 0 else 0.0
    return {'observed_interval_volume_m3': round(volume, 2),
            'covered_seconds': seconds, 'coverage_fraction': round(coverage, 5),
            'covered_interval_mean_cfs': volume / CFS_TO_CMS / seconds if seconds else None,
            'eligible_for_research_feature': coverage >= 0.9,
            'full_window_volume_not_extrapolated': True}

def summarize(rows, now):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['station_id'], row['series_id'], row['parameter_code'], row['unit'])].append(row)
    out = []
    for (station, sid, code, unit), group in sorted(groups.items()):
        group.sort(key=lambda r: r['observed_at_utc'])
        latest = group[-1]
        age = (now - utc(latest['observed_at_utc'])).total_seconds() / 60
        entry = {'station_id': station, 'series_id': sid, 'parameter_code': code,
                 'unit': unit, 'rows': len(group), 'earliest_at_utc': group[0]['observed_at_utc'],
                 'latest_at_utc': latest['observed_at_utc'], 'latest_value': latest['value'],
                 'latest_age_minutes': round(age, 2), 'fresh': 0 <= age <= 180,
                 'latest_qualifiers': latest['qualifiers']}
        if code == '00060' and unit in ('ft3/s', 'ft^3/s'):
            # Timestamp collisions with conflicting values are excluded rather than resolved silently.
            by_time = defaultdict(set)
            for row in group:
                if row['research_qc_eligible']:
                    by_time[utc(row['observed_at_utc'])].add(row['value'])
            points = [(t, next(iter(values))) for t, values in by_time.items() if len(values) == 1]
            entry['conflicting_timestamps_excluded'] = sum(len(v) > 1 for v in by_time.values())
            entry['antecedent_windows'] = {str(days): integrate(points, now - timedelta(days=days), now)
                                           for days in (1, 3, 7, 14)}
        out.append(entry)
    return out

def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'jubilee-research/2.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read(25_000_001)
            if len(payload) > 25_000_000:
                raise ValueError('Response exceeds bounded fetch limit')
            return payload
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.days <= 31:
        raise SystemExit('--days must be 1..31; use explicit archival batches for longer history')
    now = datetime.now(timezone.utc)
    params = {'format': 'json', 'sites': ','.join(SITES), 'period': 'P' + str(args.days) + 'D',
              'parameterCd': '00060,00065,45592', 'siteStatus': 'all'}
    url = 'https://waterservices.usgs.gov/nwis/iv/?' + urllib.parse.urlencode(params)
    manifest = {'schema_version': '2.0', 'started_at_utc': now.isoformat(), 'source_url': url,
                'requested_sites': list(SITES), 'production_action': 'NO_CHANGE'}
    try:
        payload = fetch(url)
        retrieved = datetime.now(timezone.utc)
        rows = normalize(json.loads(payload), retrieved, url)
        digest = hashlib.sha256(payload).hexdigest()
        archive = HERE / 'public_archive/usgs' / (digest + '.json.gz')
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(gzip.compress(payload, mtime=0))
        if rows:
            dest = HERE / 'river_forcing_normalized.csv'
            with dest.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
        summary = summarize(rows, retrieved)
        observed_sites = {r['station_id'] for r in rows}
        manifest.update({'status': 'complete' if set(SITES) <= observed_sites else 'partial',
                         'retrieved_at_utc': retrieved.isoformat(), 'raw_sha256': digest,
                         'raw_path': str(archive.relative_to(HERE)), 'normalized_rows': len(rows),
                         'parameter_counts': dict(Counter(r['parameter_code'] for r in rows)),
                         'missing_sites': sorted(set(SITES) - observed_sites), 'series': summary})
    except Exception as exc:
        manifest.update({'status': 'failed', 'error_type': type(exc).__name__, 'normalized_rows': 0})
    manifest['guardrails'] = [
        'Coffeeville 02469761 and 02469762 are pool/tailwater of the same river, never additive inflows.',
        'Claiborne discharge excludes uncomputed overtopping flow at stages above 50 ft.',
        'P means provisional, not final; reported qualifiers remain attached.',
        'No source gap is forward-filled; partial covered volume is not total-window volume.',
        'Travel-time/lag to Mobile Bay is uncalibrated. No direct Jubilee probability update.'
    ]
    (HERE / 'river_forcing_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'series'}, indent=2))
    if manifest['status'] == 'failed':
        raise SystemExit(1)

if __name__ == '__main__':
    main()

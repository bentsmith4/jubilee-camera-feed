#!/usr/bin/env python3
"""Research-only 2016 upstream forcing versus in-bay oxygen response.

No event labels, production files, or forecast thresholds are read or written.
The held-out unit is a calendar day across all bay stations; antecedent features
are strictly before the target day. The same-day comparator is descriptive and
not an operational forecast available at dawn.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import statistics
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingest_river_forcing import SITES, normalize, utc

HERE = Path(__file__).resolve().parent
WINDOWS = ((1, 3), (3, 7), (7, 14))
MONTHS = (('2016-06-01', '2016-06-30'), ('2016-07-01', '2016-07-31'),
          ('2016-08-01', '2016-08-31'))
NCEI = {
    '01': 'https://www.ncei.noaa.gov/data/oceans/archive/arc0138/0188979/1.1/data/0-data/Mobile_Bay_Station01_July2016.nc',
    '02': 'https://www.ncei.noaa.gov/data/oceans/archive/arc0138/0188979/1.1/data/0-data/Mobile_Bay_Station02_July2016.nc',
    '03': 'https://www.ncei.noaa.gov/data/oceans/archive/arc0138/0188979/1.1/data/0-data/Mobile_Bay_Station03_July2016.nc',
}
PROFILE_SOURCES = {
    '0176497': 'https://www.ncei.noaa.gov/data/oceans/archive/arc0125/0176497/1.1/data/0-data/Mobile_Bay_CTD_July2016.nc',
    '0190491': 'https://www.ncei.noaa.gov/data/oceans/archive/arc0139/0190491/1.1/data/0-data/Mobile_Bay_CTD_July2016.nc',
}
PROFILE_DATES = {'0176497': ['2016-07-14', '2016-07-19', '2016-07-21', '2016-07-28', '2016-07-30'],
                 '0190491': ['2016-07-11', '2016-07-14', '2016-07-19']}


def download(url, cache):
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (hashlib.sha256(url.encode()).hexdigest() + Path(urllib.parse.urlparse(url).path).suffix)
    if path.exists():
        payload = path.read_bytes()
    else:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'jubilee-research/2.1'}), timeout=90) as response:
            payload = response.read(30_000_001)
        if len(payload) > 30_000_000:
            raise ValueError('Bounded source download exceeded 30 MB: ' + url)
        path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def usgs_url(start, end):
    return 'https://waterservices.usgs.gov/nwis/iv/?' + urllib.parse.urlencode({
        'format': 'json', 'sites': ','.join(SITES), 'startDT': start, 'endDT': end,
        'parameterCd': '00060,00065,45592', 'siteStatus': 'all'})


def matlab_utc(value, offset_hours):
    # NCEI explicitly labels CDT/CST. Do not infer daylight saving from date.
    return datetime.fromordinal(int(value)) + timedelta(days=float(value) % 1 - 366,
                                                      hours=offset_hours)


def daily_discharge(rows, station):
    """Observed hourly segments only; no edge extrapolation or method mixing."""
    series = defaultdict(list)
    for row in rows:
        if (row['station_id'] == station and row['parameter_code'] == '00060'
                and row['research_qc_eligible'] and row['unit'] in ('ft3/s', 'ft^3/s')):
            series[row['series_id']].append(row)
    if len(series) != 1:
        return {}, {'status': 'AMBIGUOUS_OR_MISSING_METHOD', 'methods': sorted(series)}
    points = {}
    for row in next(iter(series.values())):
        t = utc(row['observed_at_utc'])
        points.setdefault(t, []).append(row)
    unique = {t: rs[0] for t, rs in points.items() if len({r['value'] for r in rs}) == 1}
    by_day = defaultdict(list)
    for t, row in unique.items():
        by_day[t.date()].append(row)
    daily = {}
    for day, group in by_day.items():
        # USGS 2016 archival records here are hourly. Require >=90% of the 24
        # hourly slots and prohibit a gap >2h, including the day's edges.
        times = sorted(utc(r['observed_at_utc']) for r in group)
        start = datetime.combine(day, datetime.min.time(), timezone.utc)
        gaps = [(times[0] - start).total_seconds(),
                *((b - a).total_seconds() for a, b in zip(times, times[1:])),
                (start + timedelta(days=1) - times[-1]).total_seconds()]
        if len(times) < 22 or max(gaps) > 7200:
            continue
        daily[day] = {'cfs': statistics.mean(float(r['value']) for r in group),
                      'samples': len(group),
                      'estimated_samples': sum(bool(r['is_estimated']) for r in group),
                      'provisional_samples': sum('P' in r['qualifiers'].split('|') for r in group)}
    return daily, {'status': 'AVAILABLE', 'method': next(iter(series)),
                   'qualified_timestamps': len(unique), 'complete_utc_days': len(daily),
                   'first': min(daily).isoformat() if daily else None,
                   'last': max(daily).isoformat() if daily else None}


def window(daily, target_day, start, end):
    days = [target_day - timedelta(days=n) for n in range(start, end)]
    if not all(day in daily for day in days):
        return None
    return statistics.mean(daily[day]['cfs'] for day in days)


def bay_daily(files):
    from netCDF4 import Dataset
    result, coverage = defaultdict(dict), {}
    for station, path in files.items():
        with Dataset(path) as ds:
            assert ds.variables['DO'].units == '%'
            assert ds.variables['time'].units.endswith('CDT')
            values = defaultdict(list)
            for t, oxygen, salinity in zip(ds.variables['time'][:], ds.variables['DO'][:], ds.variables['sal'][:]):
                if any(math.isnan(float(x)) for x in (t, oxygen, salinity)):
                    continue
                stamp = matlab_utc(t, 5)
                if stamp.year != 2016 or not 0 <= oxygen <= 200:
                    continue
                values[stamp.date()].append((float(oxygen), float(salinity)))
            for day, observations in values.items():
                if len(observations) >= 100:  # About 70% of nominal 10-minute cadence.
                    result[day][station] = {'oxygen_percent_median': statistics.median(x[0] for x in observations),
                                            'salinity_psu_median': statistics.median(x[1] for x in observations),
                                            'observations': len(observations)}
            coverage[station] = {'rows': len(ds.variables['time']), 'complete_days': sum(station in x for x in result.values()),
                                 'first_utc': min(values).isoformat(), 'last_utc': max(values).isoformat(),
                                 'oxygen_unit': '% saturation', 'source_timezone': 'CDT'}
    return result, coverage


def ridge_predict(train, test, features, penalty=0.1):
    # Scale from TRAIN only and regularize slopes. Station intercepts are
    # separate and never extrapolated from held-out target values.
    import numpy as np
    x = np.array([[1, *(int(r['station'] == s) for s in ('02', '03')),
                   *(r[f] for f in features)] for r in train], dtype=float)
    z = np.array([[1, *(int(r['station'] == s) for s in ('02', '03')),
                   *(r[f] for f in features)] for r in test], dtype=float)
    mean, scale = x[:, 3:].mean(axis=0), x[:, 3:].std(axis=0)
    scale[scale == 0] = 1
    x[:, 3:], z[:, 3:] = (x[:, 3:] - mean) / scale, (z[:, 3:] - mean) / scale
    y = np.array([r['target'] for r in train])
    regularizer = np.diag([0, 0, 0] + [penalty] * len(features))
    return z @ np.linalg.solve(x.T @ x + regularizer, x.T @ y)


def compare(daily, bay, station, interval):
    """Chronological 4-fold common-case comparison with 1-day embargo."""
    rows = []
    for day in sorted(bay):
        same = daily.get(day)
        lag = window(daily, day, *interval)
        if same is None or lag is None:
            continue
        for bay_station, obs in bay[day].items():
            rows.append({'day': day, 'station': bay_station,
                         'target': obs['oxygen_percent_median'], 'no_lag': math.log1p(same['cfs']),
                         'antecedent': math.log1p(lag), 'day_index': day.toordinal()})
    days = sorted({r['day'] for r in rows})
    if len(days) < 12:
        return {'status': 'INSUFFICIENT_OVERLAP', 'days': len(days), 'rows': len(rows)}
    errors = []
    for fold in range(4):
        held = set(days[fold * len(days) // 4:(fold + 1) * len(days) // 4])
        test = [r for r in rows if r['day'] in held]
        train = [r for r in rows if r['day'] not in held and all(abs((r['day'] - d).days) > 1 for d in held)]
        if len({r['day'] for r in train}) < 7:
            return {'status': 'INSUFFICIENT_EMBARGOED_TRAINING', 'days': len(days)}
        base = ridge_predict(train, test, ('no_lag',))
        augmented = ridge_predict(train, test, ('no_lag', 'antecedent'))
        trend_base = ridge_predict(train, test, ('no_lag', 'day_index'))
        trend_lag = ridge_predict(train, test, ('no_lag', 'day_index', 'antecedent'))
        for r, a, b, c, d in zip(test, base, augmented, trend_base, trend_lag):
            errors.append({'day': r['day'].isoformat(), 'station': r['station'],
                           'fold': fold,
                           'baseline_sq_error': (r['target'] - a)**2,
                           'lagged_sq_error': (r['target'] - b)**2,
                           'trend_baseline_sq_error': (r['target'] - c)**2,
                           'trend_lagged_sq_error': (r['target'] - d)**2})
    by_station = {}
    for key in ('01', '02', '03', 'all'):
        subset = [r for r in errors if key == 'all' or r['station'] == key]
        if not subset:
            continue
        b = statistics.mean(r['baseline_sq_error'] for r in subset)
        a = statistics.mean(r['lagged_sq_error'] for r in subset)
        tb = statistics.mean(r['trend_baseline_sq_error'] for r in subset)
        ta = statistics.mean(r['trend_lagged_sq_error'] for r in subset)
        by_station[key] = {'rows': len(subset), 'baseline_rmse': round(math.sqrt(b), 4),
                           'lagged_rmse': round(math.sqrt(a), 4),
                           'delta_mse_lag_minus_baseline': round(a - b, 4),
                           'trend_baseline_rmse': round(math.sqrt(tb), 4),
                           'trend_lagged_rmse': round(math.sqrt(ta), 4),
                           'delta_mse_lag_minus_trend_baseline': round(ta - tb, 4)}
    # Date-cluster leave-one-day-out sensitivity, not an independent confidence
    # interval: a single oxygen episode spans many adjacent days.
    deltas = []
    for day in days:
        subset = [r for r in errors if r['day'] != day.isoformat()]
        deltas.append(statistics.mean(r['lagged_sq_error'] - r['baseline_sq_error'] for r in subset))
    fold_deltas = [statistics.mean(r['lagged_sq_error'] - r['baseline_sq_error']
                                   for r in errors if r['fold'] == fold) for fold in range(4)]
    return {'status': 'EXPLORATORY', 'upstream_station': station, 'lag_days': list(interval),
            'held_out_days': len(days), 'held_out_rows': len(errors),
            'embargo_days': 1, 'metrics': by_station,
            'leave_one_day_out_delta_mse_range': [round(min(deltas), 4), round(max(deltas), 4)],
            'held_out_fold_delta_mse': [round(x, 4) for x in fold_deltas]}


def run(cache):
    retrieved = datetime.now(timezone.utc)
    source_manifest, rows = [], []
    for start, end in MONTHS:
        url = usgs_url(start, end)
        path, sha = download(url, cache)
        batch = normalize(json.loads(path.read_text()), retrieved, url)
        counts = Counter((r['station_id'], r['parameter_code']) for r in batch)
        source_manifest.append({'url': url, 'sha256': sha, 'bytes': path.stat().st_size,
                                'normalized_rows': len(batch),
                                'series_counts': {s + ':' + p: n for (s, p), n in sorted(counts.items())}})
        rows.extend(batch)
    bay_files, bay_sources = {}, []
    for station, url in NCEI.items():
        path, sha = download(url, cache)
        bay_files[station] = path
        bay_sources.append({'accession': '0188979', 'station': station, 'url': url, 'sha256': sha})
    for accession, url in PROFILE_SOURCES.items():
        path, sha = download(url, cache)
        bay_sources.append({'accession': accession, 'url': url, 'sha256': sha,
                            'survey_dates': PROFILE_DATES[accession],
                            'role': 'Sparse profile dates overlap archival river history but cannot independently identify a lag; excluded from fitted lag. 0176497 oxygen is mg/L and source clock CST; 0190491 oxygen is percent saturation and clock CDT. Never pool units or silently shift CST.'})
    bay, bay_coverage = bay_daily(bay_files)
    discharges, coverage = {}, {}
    for station in SITES:
        discharges[station], coverage[station] = daily_discharge(rows, station)
        station_rows = [r for r in rows if r['station_id'] == station and r['parameter_code'] == '00060']
        coverage[station]['raw_discharge_rows'] = len(station_rows)
        coverage[station]['estimated_rows'] = sum(bool(r['is_estimated']) for r in station_rows)
        coverage[station]['provisional_rows'] = sum('P' in r['qualifiers'].split('|') for r in station_rows)
    findings = {station: [compare(discharges[station], bay, station, interval) for interval in WINDOWS]
                for station in SITES}
    manifest = {'schema_version': '1.0', 'scope': 'RESEARCH_ONLY_RIVER_BAY_LAG_2016',
                'generated_at_utc': retrieved.isoformat(), 'production_action': 'NO_CHANGE',
                'usgs_batches': source_manifest, 'ncei_sources': bay_sources,
                'usgs_daily_coverage': coverage, 'bay_coverage': bay_coverage,
                'non_additivity': '02469761 Coffeeville pool and 02469762 tailwater are the same river; never sum.',
                'estimated_provisional_policy': 'Preserved row-level through normalization; complete daily features include qualified A/P/e with no interpolation.',
                'source_availability': 'Historical retrospective only; not a contemporaneously available operational feature.'}
    report = {'scope': manifest['scope'], 'production_action': 'NO_CHANGE',
              'target': 'NCEI 0188979 daily median DO percent saturation; not mg/L or Jubilee labels',
              'comparison': 'Same-day discharge baseline versus same-day plus strictly antecedent discharge, on identical rows; parallel linear calendar-trend sensitivity; blocked four-fold date holdout, one-day embargo.',
              'candidate_windows_days_before_target': [list(w) for w in WINDOWS],
              'findings': findings,
              'interpretation_limit': 'One short deployment and serially dependent stations/days cannot identify physical travel time. Windows are association tests, not arrival-time estimates; survey profiles are too sparse for independent fitting.',
              'promotion_eligible': False}
    return manifest, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', type=Path, required=True, help='Local untracked immutable source cache')
    parser.add_argument('--out-dir', type=Path, default=HERE)
    args = parser.parse_args()
    manifest, report = run(args.cache_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (('river_bay_lag_2016_manifest.json', manifest), ('river_bay_lag_2016_findings.json', report)):
        (args.out_dir / name).write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'coverage': manifest['usgs_daily_coverage'], 'findings': report['findings']}, indent=2))


if __name__ == '__main__':
    main()

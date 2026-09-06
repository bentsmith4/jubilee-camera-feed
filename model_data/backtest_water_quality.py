#!/usr/bin/env python3
"""Research diagnostic, NOT a validated forecast backtest.

Excludes event-day samples; counts unique rows separately from repeated lag
memberships; never labels unreported dates as non-events; requires explicit
station/event mappings before producing geographically matched comparisons.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
LAGS = (1, 3, 7, 14)

def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None

def as_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None

def row_key(row):
    if row.get('observation_id'):
        return row['observation_id']
    keys = ('source_id', 'station_id', 'activity_id', 'result_id', 'sample_date',
            'sample_time', 'parameter', 'value', 'unit', 'depth', 'depth_unit', 'method', 'qc_or_status')
    return hashlib.sha256(json.dumps({k: row.get(k, '') for k in keys}, sort_keys=True).encode()).hexdigest()

def transform(parameter, value):
    if any(word in (parameter or '').lower() for word in ('enterococcus', 'enterococci')):
        return (math.log10(value), 'log10_raw_value') if value > 0 else (None, 'nonpositive_not_imputed')
    return value, 'raw_value'

def antecedent(sample_date, event_date, lag_days):
    return event_date - timedelta(days=lag_days) <= sample_date < event_date

def validation_blocks(events):
    """Conservative temporal blocks, not a claim of physical event independence."""
    blocks, last, block = {}, None, 0
    for event in sorted(events, key=lambda e: e['_date']):
        if last is None or (event['_date'] - last).days > max(LAGS):
            block += 1
        blocks[event['event_id']] = block
        last = event['_date']
    return blocks

def analyze(raw_rows, event_document):
    events = []
    for event in event_document.get('events', []):
        d = parse_date(event.get('event_date_ct'))
        if d and event.get('classification') == 'confirmed_jubilee':
            events.append({**event, '_date': d})
    unique, excluded, duplicates = {}, defaultdict(int), 0
    for row in raw_rows:
        d, v = parse_date(row.get('sample_date')), as_float(row.get('value'))
        if d is None or v is None:
            excluded['invalid_date_or_nonfinite_value'] += 1
            continue
        if row.get('detection_condition') or row.get('value_qualifier'):
            excluded['censored_or_qualified_value_requires_separate_analysis'] += 1
            continue
        tv, name = transform(row.get('parameter'), v)
        if tv is None:
            excluded['nonpositive_microbiology_not_imputed'] += 1
            continue
        k = row_key(row)
        if k in unique:
            duplicates += 1
            continue
        unique[k] = {**row, '_date': d, '_value': tv, '_key': k, '_transform': name}
    rows = list(unique.values())
    event_ids, linked_keys, memberships = set(), set(), 0
    mapped_pairs = defaultdict(dict)
    same_day = set()
    for event in events:
        mapped_stations = set(event.get('analysis_station_ids', []))
        for row in rows:
            if row['_date'] == event['_date']:
                same_day.add((event['event_id'], row['_key']))
            for lag in LAGS:
                if not antecedent(row['_date'], event['_date'], lag):
                    continue
                memberships += 1
                event_ids.add(event['event_id'])
                linked_keys.add(row['_key'])
                if row.get('station_id') not in mapped_stations:
                    continue
                group = (lag, row.get('source_id'), row.get('station_id'), row.get('parameter'),
                         row.get('unit'), row.get('method'), row['_transform'])
                mapped_pairs[group][row['_key']] = row
    results = []
    dates = [e['_date'] for e in events]
    for group, event_rows in mapped_pairs.items():
        lag, source, station, parameter, unit, method, transform_name = group
        months = {e['_date'].month for e in events if station in e.get('analysis_station_ids', [])}
        background = [r['_value'] for r in rows
                      if (r.get('source_id'), r.get('station_id'), r.get('parameter'), r.get('unit'), r.get('method'))
                      == (source, station, parameter, unit, method)
                      and r['_date'].month in months
                      and all(abs((r['_date'] - d).days) > max(LAGS) for d in dates)]
        if not background:
            continue
        ev, bg = median(r['_value'] for r in event_rows.values()), median(background)
        delta = ev - bg
        results.append({'lag_days': lag, 'source_id': source, 'station_id': station,
                        'parameter': parameter, 'unit': unit, 'method': method,
                        'transform': transform_name, 'unique_event_observations': len(event_rows),
                        'unlabelled_background_observations': len(background),
                        'event_median': ev, 'background_median': bg,
                        'median_difference': delta,
                        'direction': 'no_difference' if math.isclose(ev, bg, rel_tol=1e-9, abs_tol=1e-12)
                                     else ('higher' if delta > 0 else 'lower'),
                        'predictive_validity': 'NOT_ESTABLISHED'})
    blocks = validation_blocks(events)
    return {
        'schema_version': '2.0', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Strictly pre-event-date exploratory coverage; explicit station mappings; unlabelled background, not verified negatives.',
        'confirmed_events_in_database': len(events),
        'confirmed_events_with_any_water_quality_data': len(event_ids),
        'event_linked_observations_across_tests': memberships,
        'unique_event_linked_observations': len(linked_keys),
        'temporal_overlap_is_not_geographic_match': True,
        'conservative_temporal_validation_blocks': len(set(blocks.values())),
        'same_day_event_sample_pairs_excluded': len(same_day),
        'duplicate_rows_excluded': duplicates, 'excluded_rows': dict(excluded),
        'input_unique_numeric_rows': len(rows),
        'events_with_explicit_station_mapping': sum(bool(e.get('analysis_station_ids')) for e in events),
        'verified_matched_non_event_count': 0,
        'prospective_availability_validated': False,
        'sufficient_for_production_promotion': False, 'production_action': 'NO_CHANGE',
        'guardrail': 'No production promotion. Collection date is not result-availability date; unreported dates are not confirmed non-events.',
        'required_before_formal_validation': [
            'QC/detection-limit-aware measurements and collection depths',
            'individually evidenced event dates and explicit station/cell matching',
            'documented observation effort for non-events',
            'result publication/availability timestamps before forecast cutoff',
            'blocked out-of-sample evaluation by episode and season',
            'baseline comparison using Brier score, calibration, precision/recall and useful lead time'
        ],
        'results': results
    }

def main():
    data = HERE / 'water_quality_normalized.csv'
    if not data.exists():
        raise SystemExit('Missing normalized dataset; refusing to report an empty successful backtest.')
    with data.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    report = analyze(rows, json.loads((HERE / 'event_history.json').read_text(encoding='utf-8')))
    (HERE / 'water_quality_backtest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Provenance-first public WQP research ingestion; never changes forecasts."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WQP = 'https://www.waterqualitydata.us/data/Result/search'
OFFSETS = {'UTC': 0, 'GMT': 0, 'CST': -6, 'CDT': -5, 'EST': -5, 'EDT': -4}

def first(row, *keys):
    return next((row[k] for k in keys if row.get(k) not in (None, '')), '')

def as_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def sample_utc(day, clock, zone):
    if not day or not clock or zone not in OFFSETS:
        return None
    try:
        dt = datetime.fromisoformat(day + 'T' + clock)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).isoformat()
        return dt.replace(tzinfo=timezone(timedelta(hours=OFFSETS[zone]))).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None

def read_csv(payload, required):
    text = payload.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
        raise ValueError('Unexpected CSV schema; refusing to ingest an error/login page')
    rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError('Malformed CSV row has extra columns')
    return rows

def normalize(payload, source_id, station_cell, source_url, retrieved_at, station_meta=None):
    records = read_csv(payload, ('MonitoringLocationIdentifier', 'CharacteristicName', 'ActivityStartDate'))
    station_meta = station_meta or {}
    rows = []
    for raw in records:
        station = raw['MonitoringLocationIdentifier']
        if station not in station_cell:
            raise ValueError('Unexpected station in downloaded results')
        meta = station_meta.get(station, {})
        day = raw.get('ActivityStartDate', '')
        clock, zone = raw.get('ActivityStartTime/Time', ''), raw.get('ActivityStartTime/TimeZoneCode', '')
        raw_value = raw.get('ResultMeasureValue', '')
        qualifier = re.match(r'^\s*([<>]=?)', raw_value or '')
        detection = raw.get('ResultDetectionConditionText', '')
        identity = hashlib.sha256(json.dumps({'source_id': source_id, 'row': raw}, sort_keys=True).encode()).hexdigest()
        rows.append({
            'observation_id': identity, 'source_id': source_id, 'provider': 'Water Quality Portal/STORET',
            'station_id': station, 'station_name': first(raw, 'MonitoringLocationName') or meta.get('MonitoringLocationName', ''),
            'shoreline_cell': station_cell[station], 'activity_id': raw.get('ActivityIdentifier', ''),
            'result_id': raw.get('ResultIdentifier', ''), 'sample_date': day, 'sample_time': clock,
            'sample_timezone': zone, 'sample_datetime_utc': sample_utc(day, clock, zone),
            'parameter': raw.get('CharacteristicName', ''), 'raw_value': raw_value,
            'value': as_float(raw_value) if not qualifier else None,
            'value_qualifier': qualifier.group(1) if qualifier else '',
            'detection_condition': detection,
            'detection_limit_value': first(raw, 'DetectionQuantitationLimitMeasure/MeasureValue'),
            'detection_limit_unit': first(raw, 'DetectionQuantitationLimitMeasure/MeasureUnitCode'),
            'unit': first(raw, 'ResultMeasure/MeasureUnitCode', 'MeasureUnitCode'),
            'latitude': as_float(first(raw, 'LatitudeMeasure') or meta.get('LatitudeMeasure')),
            'longitude': as_float(first(raw, 'LongitudeMeasure') or meta.get('LongitudeMeasure')),
            'coordinate_datum': first(raw, 'HorizontalCoordinateReferenceSystemDatumName') or meta.get('HorizontalCoordinateReferenceSystemDatumName', ''),
            'depth': as_float(raw.get('ActivityDepthHeightMeasure/MeasureValue')),
            'depth_unit': raw.get('ActivityDepthHeightMeasure/MeasureUnitCode', ''),
            'vertical_reference': raw.get('ActivityDepthAltitudeReferencePointText', ''),
            'qc_or_status': raw.get('ResultStatusIdentifier', ''),
            'status_is_not_sensor_qc': True,
            'result_value_type': raw.get('ResultValueTypeName', ''),
            'result_qualifier_raw': first(raw, 'MeasureQualifierCode', 'ResultMeasureQualifierCode'),
            'activity_type': raw.get('ActivityTypeCode', ''), 'media': raw.get('ActivityMediaName', ''),
            'method': raw.get('ResultAnalyticalMethod/MethodIdentifier', ''),
            'organization': raw.get('OrganizationIdentifier', ''),
            'source_url': source_url, 'raw_response_sha256': hashlib.sha256(payload).hexdigest(),
            'ingested_at_utc': retrieved_at, 'available_at_utc': '',
            'availability_status': 'historical_publication_time_unknown',
            'production_weight': 0.0
        })
    return rows

def wqp_url(stations, resource='Result'):
    params = {'siteid': ';'.join(stations), 'mimeType': 'csv', 'zip': 'no', 'providers': 'STORET', 'sorted': 'no'}
    return 'https://www.waterqualitydata.us/data/' + resource + '/search?' + urllib.parse.urlencode(params, safe=';')

def fetch(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'jubilee-research/2.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                payload = response.read(30_000_001)
            if len(payload) > 30_000_000:
                raise ValueError('Response exceeds bounded download limit')
            return payload
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def archive(payload, kind):
    digest = hashlib.sha256(payload).hexdigest()
    path = HERE / 'public_archive/wqp' / (kind + '-' + digest + '.csv.gz')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(gzip.compress(payload, mtime=0))
    return {'path': str(path.relative_to(HERE)), 'sha256': digest, 'bytes': len(payload)}

def write_csv(rows, path):
    if not rows:
        raise ValueError('Refusing to replace a dataset with an empty successful snapshot')
    tmp = path.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    reg = json.loads((HERE / 'water_quality_sources.json').read_text(encoding='utf-8'))
    (HERE / 'raw_water_quality').mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    manifest = {'schema_version': '2.0', 'started_at_utc': started, 'sources': [], 'unimplemented_sources': []}
    all_rows = {}
    for source in reg['source_families']:
        if 'waterqualitydata.us' not in source.get('endpoint', ''):
            manifest['unimplemented_sources'].append({'source_id': source['source_id'], 'status': 'REFERENCED_NOT_INGESTED'})
            continue
        stations = [s['station_id'] for s in source['stations']]
        cells = {s['station_id']: s.get('shoreline_cell', 'regional') for s in source['stations']}
        url = wqp_url(stations)
        entry = {'source_id': source['source_id'], 'url': url, 'stations': stations}
        if args.dry_run:
            print(json.dumps(entry)); continue
        try:
            payload = fetch(url)
            stamp = datetime.now(timezone.utc).isoformat()
            # Validate before saving to the current raw filename.
            read_csv(payload, ('MonitoringLocationIdentifier', 'CharacteristicName', 'ActivityStartDate'))
            entry['raw_archive'] = archive(payload, source['source_id'].lower() + '-results')
            raw_path = HERE / 'raw_water_quality' / (source['source_id'].lower() + '.csv')
            raw_path.write_bytes(payload)
            station_meta = {}
            try:
                station_payload = fetch(wqp_url(stations, 'Station'))
                metadata_rows = read_csv(station_payload, ('MonitoringLocationIdentifier', 'LatitudeMeasure', 'LongitudeMeasure'))
                station_meta = {r['MonitoringLocationIdentifier']: r for r in metadata_rows}
                entry['station_archive'] = archive(station_payload, source['source_id'].lower() + '-stations')
                entry['station_metadata_status'] = 'retrieved'
            except Exception as exc:
                entry['station_metadata_status'] = 'unavailable_' + type(exc).__name__
            rows = normalize(payload, source['source_id'], cells, url, stamp, station_meta)
            if not rows:
                raise ValueError('Source returned zero observations')
            for row in rows:
                all_rows[row['observation_id']] = row
            entry.update({'status': 'ok', 'raw_path': str(raw_path.relative_to(HERE)), 'rows': len(rows),
                          'censored_or_detection_flag_rows': sum(bool(r['detection_condition'] or r['value_qualifier']) for r in rows),
                          'missing_depth_rows': sum(r['depth'] is None for r in rows),
                          'missing_coordinates_rows': sum(r['latitude'] is None or r['longitude'] is None for r in rows)})
        except Exception as exc:
            entry.update({'status': 'error', 'error_type': type(exc).__name__})
        manifest['sources'].append(entry)
    if args.dry_run:
        return
    successes = sum(e.get('status') == 'ok' for e in manifest['sources'])
    rows = list(all_rows.values())
    if rows:
        write_csv(rows, HERE / 'water_quality_normalized.csv')
    manifest.update({'finished_at_utc': datetime.now(timezone.utc).isoformat(),
                     'normalized_rows': len(rows),
                     'status': 'complete' if successes == len(manifest['sources']) and successes else ('partial' if successes else 'failed'),
                     'production_action': 'NO_CHANGE',
                     'coverage_scope': 'Only the listed WQP requests; referenced PDF sources are NOT included.'})
    (HERE / 'water_quality_ingest_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))
    if manifest['status'] != 'complete':
        raise SystemExit(1)

if __name__ == '__main__':
    main()

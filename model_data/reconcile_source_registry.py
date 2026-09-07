#!/usr/bin/env python3
"""Reconcile the canonical source registry from verified ingestion manifests.

The registry is descriptive state derived from successful parser manifests. A
URL or discovery record is never promoted by this script. Evidence class,
freshness, hashes, row counts and parser provenance are preserved, and model
outputs remain MODEL with zero production weight.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / 'ongoing_source_registry_20260906.json'


def load(name):
    p = HERE / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def completed(manifest):
    return bool(manifest and manifest.get('status') == 'complete')


def manifest_time(manifest):
    if not manifest:
        return None
    return manifest.get('retrieved_at') or manifest.get('retrieved_at_utc') or manifest.get('started_at_utc')


def main():
    doc = json.loads(REGISTRY.read_text(encoding='utf-8'))
    by_id = {x.get('source_id'): x for x in doc.get('sources', [])}
    changes = []

    def mark(source_id, **updates):
        row = by_id.get(source_id)
        if row is None:
            raise SystemExit(f'Canonical source registry missing {source_id}')
        changed = {}
        for key, value in updates.items():
            if value is None:
                continue
            if row.get(key) != value:
                row[key] = value
                changed[key] = value
        if changed:
            changes.append({'source_id': source_id, 'updates': changed})

    # Static direct CTD profiles.
    main_pass = load('griidc_main_pass_20160419_manifest.json')
    if completed(main_pass):
        mark(
            'griidc_r4_x260_000_0055_main_pass_2016',
            status='INGESTED',
            ingestion_status='complete',
            evidence_class='DIRECT_at_cast_location_time_depth',
            last_verified_at=manifest_time(main_pass),
            normalized_rows=main_pass.get('normalized_rows'),
            profile_count=main_pass.get('profile_count'),
            raw_object_count=len(main_pass.get('raw_objects', [])),
            ingestion_manifest='model_data/griidc_main_pass_20160419_manifest.json',
            normalized_data='model_data/griidc_main_pass_20160419_normalized.csv',
            production_weight=0.0,
        )

    # Realtime Weeks Bay observations. Keep them a regional proxy for the
    # open-Bay Eastern Shore and preserve source-level hashes/last observations.
    weeks = load('weeks_bay_realtime_manifest.json')
    if completed(weeks):
        station_rows = {x.get('station_id'): x.get('normalized_rows') for x in weeks.get('sources', [])}
        station_hashes = {x.get('station_id'): x.get('raw_sha256') for x in weeks.get('sources', [])}
        latest = {x.get('station_id'): x.get('latest_observed_at') for x in weeks.get('sources', [])}
        mark(
            'weeks_bay_nerr_swmp',
            status='PARTIALLY_INGESTED_REALTIME',
            ingestion_status='NDBC_realtime_WKQA1_WKXA1_parser_complete; final_CDME_archive_not_yet_ingested',
            last_verified_at=manifest_time(weeks),
            realtime_normalized_rows=weeks.get('normalized_rows'),
            realtime_station_rows=station_rows,
            realtime_raw_sha256=station_hashes,
            realtime_latest_observed_at=latest,
            ingestion_manifest='model_data/weeks_bay_realtime_manifest.json',
            production_weight=0.0,
        )

    # River forcing is one physical forcing system with multiple series; update
    # both registry entries without double-counting it as independent evidence.
    river = load('river_forcing_manifest.json')
    if completed(river):
        series = river.get('series', [])
        per_station = {}
        for s in series:
            sid = s.get('station_id')
            if not sid:
                continue
            row = per_station.setdefault(sid, {'rows': 0, 'fresh_series': 0, 'latest_at_utc': None, 'parameters': set()})
            row['rows'] += int(s.get('rows') or 0)
            row['fresh_series'] += int(bool(s.get('fresh')))
            row['parameters'].add(s.get('parameter_code'))
            latest = s.get('latest_at_utc')
            if latest and (row['latest_at_utc'] is None or latest > row['latest_at_utc']):
                row['latest_at_utc'] = latest
        serial = {k: {**v, 'parameters': sorted(x for x in v['parameters'] if x)} for k, v in per_station.items()}
        common = dict(
            ingestion_status='complete_recent_USGS_IV',
            last_verified_at=manifest_time(river),
            raw_sha256=river.get('raw_sha256'),
            normalized_rows=river.get('normalized_rows'),
            station_health=serial,
            ingestion_manifest='model_data/river_forcing_manifest.json',
            production_weight=0.0,
        )
        mark('usgs_02428400_claiborne', status='INGESTED_RECENT', **common)
        mark('usgs_02469761_02469762_coffeeville', status='INGESTED_RECENT_SOURCE_HEALTH_VARIES_BY_SERIES', **common)

    # NGOFS2 is MODEL guidance. Current named-point extraction is useful but is
    # not allowed to masquerade as shoreline-grid resolution.
    pc_now = load('ngofs2_point_clear_nowcast_manifest.json')
    pc_fc = load('ngofs2_point_clear_forecast_manifest.json')
    multi_now = load('ngofs2_mobile_bay_named_stations_nowcast_manifest.json')
    multi_fc = load('ngofs2_mobile_bay_named_stations_forecast_manifest.json')
    point_clear_ok = completed(pc_now) and completed(pc_fc)
    multicell_ok = completed(multi_now) and completed(multi_fc)
    if point_clear_ok or multicell_ok:
        status = 'PARTIALLY_INGESTED_POINT_CLEAR' if point_clear_ok else 'REGISTERED'
        if multicell_ok:
            status = 'PARTIALLY_INGESTED_MOBILE_BAY_NAMED_POINTS'
        unresolved = []
        if multicell_ok:
            unresolved.extend(multi_now.get('unresolved_targets', []))
            unresolved.extend(multi_fc.get('unresolved_targets', []))
        mark(
            'noaa_ngofs2_mobile_bay',
            status=status,
            observation_status='MODEL',
            last_verified_at=max(x for x in [manifest_time(pc_now), manifest_time(pc_fc), manifest_time(multi_now), manifest_time(multi_fc)] if x),
            point_clear_nowcast_rows=pc_now.get('normalized_rows') if pc_now else None,
            point_clear_forecast_rows=pc_fc.get('normalized_rows') if pc_fc else None,
            named_station_nowcast_rows=multi_now.get('normalized_rows') if multicell_ok else None,
            named_station_forecast_rows=multi_fc.get('normalized_rows') if multicell_ok else None,
            named_station_count=multi_now.get('station_count') if multicell_ok else None,
            named_station_unresolved_targets=unresolved if multicell_ok else None,
            point_clear_manifest='model_data/ngofs2_point_clear_nowcast_manifest.json' if point_clear_ok else None,
            named_station_manifest='model_data/ngofs2_mobile_bay_named_stations_nowcast_manifest.json' if multicell_ok else None,
            shoreline_grid_status='NOT_YET_VALIDATED',
            production_weight=0.0,
        )

    doc['schema_version'] = '1.3'
    doc['last_reconciled_at'] = datetime.now(timezone.utc).isoformat()
    doc['registry_rule'] = 'INGESTED requires a successful parser/extractor run, immutable source hash/subset hash where applicable, normalized rows and provenance manifest. Discovery alone never qualifies.'
    doc['last_reconciliation_changes'] = changes
    REGISTRY.write_text(json.dumps(doc, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'complete', 'changes': changes, 'source_count': len(doc.get('sources', []))}, indent=2))


if __name__ == '__main__':
    main()

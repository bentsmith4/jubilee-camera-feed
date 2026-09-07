#!/usr/bin/env python3
"""Reconcile the canonical source registry from verified ingestion manifests.

This updates status/provenance only when an actual parser run completed.  It
never upgrades a discovered URL to INGESTED and never changes production
weights.
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
            if row.get(key) != value:
                row[key] = value; changed[key] = value
        if changed:
            changes.append({'source_id': source_id, 'updates': changed})

    main_pass = load('griidc_main_pass_20160419_manifest.json')
    if main_pass and main_pass.get('status') == 'complete':
        mark(
            'griidc_r4_x260_000_0055_main_pass_2016',
            status='INGESTED',
            ingestion_status='complete',
            evidence_class='DIRECT_at_cast_location_time_depth',
            normalized_rows=main_pass.get('normalized_rows'),
            profile_count=main_pass.get('profile_count'),
            raw_object_count=len(main_pass.get('raw_objects', [])),
            ingestion_manifest='model_data/griidc_main_pass_20160419_manifest.json',
            normalized_data='model_data/griidc_main_pass_20160419_normalized.csv',
            production_weight=0.0,
        )

    weeks = load('weeks_bay_realtime_manifest.json')
    if weeks and weeks.get('status') == 'complete':
        station_rows = {x.get('station_id'): x.get('normalized_rows') for x in weeks.get('sources', [])}
        mark(
            'weeks_bay_nerr_swmp',
            status='PARTIALLY_INGESTED_REALTIME',
            ingestion_status='NDBC_realtime_WKQA1_WKXA1_parser_complete; full_final_CDME_archive_not_yet_ingested',
            realtime_normalized_rows=weeks.get('normalized_rows'),
            realtime_station_rows=station_rows,
            ingestion_manifest='model_data/weeks_bay_realtime_manifest.json',
            production_weight=0.0,
        )

    pc_now = load('ngofs2_point_clear_nowcast_manifest.json')
    pc_fc = load('ngofs2_point_clear_forecast_manifest.json')
    multi_now = load('ngofs2_mobile_bay_named_stations_nowcast_manifest.json')
    multi_fc = load('ngofs2_mobile_bay_named_stations_forecast_manifest.json')
    point_clear_ok = bool(pc_now and pc_fc and pc_now.get('status') == 'complete' and pc_fc.get('status') == 'complete')
    multicell_ok = bool(multi_now and multi_fc and multi_now.get('status') == 'complete' and multi_fc.get('status') == 'complete')
    if point_clear_ok or multicell_ok:
        status = 'PARTIALLY_INGESTED_POINT_CLEAR' if point_clear_ok else 'REGISTERED'
        if multicell_ok:
            status = 'PARTIALLY_INGESTED_MOBILE_BAY_NAMED_POINTS'
        mark(
            'noaa_ngofs2_mobile_bay',
            status=status,
            observation_status='MODEL',
            point_clear_nowcast_rows=pc_now.get('normalized_rows') if pc_now else None,
            point_clear_forecast_rows=pc_fc.get('normalized_rows') if pc_fc else None,
            named_station_nowcast_rows=multi_now.get('normalized_rows') if multicell_ok else None,
            named_station_forecast_rows=multi_fc.get('normalized_rows') if multicell_ok else None,
            named_station_count=multi_now.get('station_count') if multicell_ok else None,
            point_clear_manifest='model_data/ngofs2_point_clear_nowcast_manifest.json' if point_clear_ok else None,
            named_station_manifest='model_data/ngofs2_mobile_bay_named_stations_nowcast_manifest.json' if multicell_ok else None,
            production_weight=0.0,
        )

    doc['schema_version'] = '1.2'
    doc['last_reconciled_at'] = datetime.now(timezone.utc).isoformat()
    doc['registry_rule'] = 'INGESTED requires a successful parser/extractor run, immutable source hash/subset hash where applicable, normalized rows and provenance manifest. Discovery alone never qualifies.'
    doc['last_reconciliation_changes'] = changes
    REGISTRY.write_text(json.dumps(doc, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'status':'complete','changes':changes,'source_count':len(doc.get('sources', []))}, indent=2))


if __name__ == '__main__':
    main()

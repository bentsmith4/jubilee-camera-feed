#!/usr/bin/env python3
"""Report what this job actually verified; never infer desktop deployment."""
import datetime
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

def read(name):
    path = HERE / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def main():
    c, r, t = read('sensing_audit.json'), read('river_forcing_manifest.json'), read('upgrade_test_report.json')
    reg, w, b = read('camera_sources.json'), read('water_quality_ingest_manifest.json'), read('water_quality_backtest.json')
    private = c.get('private_cameras', [])
    passing = [x for x in private if x.get('upstream_metadata_pass')]
    coverage = []
    for cell in ('Daphne', 'Montrose', 'Fairhope', 'Battles Wharf', 'Point Clear', 'Mullet Point'):
        cams = [x for x in passing if x.get('shoreline_cell') == cell]
        coverage.append({
            'cell': cell,
            'private_camera_metadata_passing_ids': [x['camera_id'] for x in cams],
            'independent_private_site_groups': sorted({x['site_group'] for x in cams}),
            'public_candidates_not_production_evidence': [x['camera_id'] for x in reg.get('cameras', [])
                if x.get('access') == 'public_viewer' and x.get('shoreline_cell') == cell],
            'direct_local_bottom_DO': 'NOT_VERIFIED_IN_THIS_PIPELINE',
            'direct_local_salinity_profile': 'NOT_VERIFIED_IN_THIS_PIPELINE',
            'current_transport': 'EXTERNAL_MODEL_OR_OBSERVATION_INTEGRATION_NOT_AUDITED_HERE',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'PRESENT' if cams and all(not x['missing_human_sensor_fields'] for x in cams) else 'MISSING_OR_UNVERIFIED',
            'private_archive_restore': 'NOT_VERIFIED_BY_THIS_JOB',
            'same_day_social_reports': 'EXTERNAL_INTAKE_NOT_AUDITED_BY_THIS_JOB',
            'verified_non_event_calibration': 'NOT_ESTABLISHED'
        })
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = {
        'generated_at_utc': now, 'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
        'input_commit_sha': os.environ.get('GITHUB_SHA'),
        'camera_snapshot_main_commit': os.environ.get('CAMERA_SNAPSHOT_SHA'),
        'tests': t, 'camera_metadata_status': c.get('status'),
        'private_metadata_pass': c.get('private_metadata_pass'),
        'expected_private_including_pending_onboarding': c.get('expected_private_cameras'),
        'passing_site_groups': c.get('passing_site_groups'),
        'new_montrose_camera_metadata_pass': any(x['camera_id'] == 'montrose_shoreline' for x in passing),
        'river_status': r.get('status'), 'river_rows': r.get('normalized_rows'),
        'river_parameter_counts': r.get('parameter_counts'),
        'river_distinct_series_including_gate_methods': len(r.get('series', [])),
        'desktop_modified_by_this_job': False, 'google_device_inventory_accessed_by_this_job': False,
        'public_camera_pixels_captured_by_this_job': False,
        'chatgpt_automations_modified_by_this_job': False, 'forecast_weights_changed': False,
        'private_media_uploaded_by_this_job': False,
        'raw_public_archive_path': 'model_data/public_archive',
        'water_quality_manifest_as_of': w.get('finished_at_utc'),
        'water_quality_status': w.get('status'), 'water_quality_rows': w.get('normalized_rows'),
        'water_quality_unique_event_linked_rows': b.get('unique_event_linked_observations'),
        'water_quality_same_day_pairs_excluded': b.get('same_day_event_sample_pairs_excluded'),
        'water_quality_predictive_validity': 'NOT_ESTABLISHED',
        'private_camera_archive_note': 'Historical R2 archive exists; no current restore or permission check was performed by this cloud job.'
    }
    (HERE / 'upgrade_readiness.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (HERE / 'coverage_snapshot.json').write_text(json.dumps({'generated_at_utc': now, 'cells': coverage}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()

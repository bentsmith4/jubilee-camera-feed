#!/usr/bin/env python3
"""Report what this job actually verified; never infer desktop deployment or forecast skill."""
import datetime
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    path = HERE / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def public_candidates(reg, aliases):
    aliases = set(aliases)
    return [x.get('camera_id') for x in reg.get('cameras', [])
            if x.get('access') == 'public_viewer' and x.get('shoreline_cell') in aliases]


def main():
    c, r, t = read('sensing_audit.json'), read('river_forcing_manifest.json'), read('upgrade_test_report.json')
    reg, w, b = read('camera_sources.json'), read('water_quality_ingest_manifest.json'), read('water_quality_backtest.json')
    private = c.get('private_cameras', [])
    passing = [x for x in private if x.get('upstream_metadata_pass')]

    def cams(*cells):
        selected = [x for x in passing if x.get('shoreline_cell') in cells]
        return [x['camera_id'] for x in selected], sorted({x['site_group'] for x in selected})

    daphne_cams, daphne_groups = cams('Daphne', 'Daphne/May Day')
    montrose_cams, montrose_groups = cams('Montrose')
    fairhope_cams, fairhope_groups = cams('Fairhope', 'Fairhope Pier')
    battles_cams, battles_groups = cams('Battles Wharf')
    point_cams, point_groups = cams('Point Clear', 'Point Clear/Grand Hotel')
    mullet_cams, mullet_groups = cams('Mullet Point')

    common_missing = {
        'direct_local_bottom_DO': 'MISSING',
        'direct_local_salinity_profile': 'MISSING',
        'direct_local_temperature_profile': 'MISSING',
        'direct_local_vertical_gradient': 'MISSING',
        'verified_non_event_calibration': 'NOT_ESTABLISHED'
    }

    coverage = [
        {
            'cell': 'Daphne/May Day',
            'private_camera_metadata_passing_ids': daphne_cams,
            'independent_private_site_groups': daphne_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Daphne']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'MISSING_OR_UNVERIFIED' if not daphne_cams else 'PRESENT',
            'same_day_social_reports': 'HUMAN_EXTERNAL_INTAKE',
            'historical_calibration': 'LIMITED_DATED_LOCAL_AND_CORRIDOR_EVENTS',
            'highest_value_gap': 'near-bottom DO+salinity+temperature at Daphne/May Day'
        },
        {
            'cell': 'Montrose',
            'private_camera_metadata_passing_ids': montrose_cams,
            'independent_private_site_groups': montrose_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Montrose']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'POINT_CLEAR_OR_MODEL_PROXY',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'PRESENT' if montrose_cams and all(not x.get('missing_human_sensor_fields') for x in passing if x.get('shoreline_cell') == 'Montrose') else 'MISSING_OR_UNVERIFIED',
            'same_day_social_reports': 'HUMAN_EXTERNAL_INTAKE',
            'historical_calibration': '1972_DAPHNE_MONTROSE_PLUS_2026_LOCAL_EVIDENCE',
            'highest_value_gap': 'co-located near-bottom DO+salinity and local transport/current'
        },
        {
            'cell': 'Fairhope/Fly Creek/Pier',
            'private_camera_metadata_passing_ids': fairhope_cams,
            'independent_private_site_groups': fairhope_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Fairhope']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'POINT_CLEAR_OR_MODEL_PROXY',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'MISSING_OR_UNVERIFIED',
            'same_day_social_reports': 'HUMAN_HIGH_VALUE_MODERN_EVENT_REPORTING',
            'historical_calibration': 'MULTIPLE_MODERN_DATED_EVENT_LABELS_PHYSICAL_MATCHING_SPARSE',
            'highest_value_gap': 'direct bottom sensor plus validated public-camera ROI/freshness'
        },
        {
            'cell': 'Battles Wharf',
            'private_camera_metadata_passing_ids': battles_cams,
            'independent_private_site_groups': battles_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Battles Wharf']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'POINT_CLEAR_OR_MODEL_PROXY',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'MISSING_OR_UNVERIFIED',
            'same_day_social_reports': 'HUMAN_EXTERNAL_INTAKE',
            'historical_calibration': 'SPARSE_DATED_JUBILEE_LABELS',
            'highest_value_gap': 'historical event recovery and reliable shoreline sensing'
        },
        {
            'cell': 'Point Clear/Grand Hotel',
            'private_camera_metadata_passing_ids': point_cams,
            'independent_private_site_groups': point_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Point Clear']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'OFFICIAL_TIDE_REFERENCE_GEOMETRY_OBSERVED_LEVEL_CHECK_SEPARATELY',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'PRESENT' if point_cams and all(not x.get('missing_human_sensor_fields') for x in passing if x.get('shoreline_cell') == 'Point Clear') else 'MISSING_OR_UNVERIFIED',
            'same_day_social_reports': 'HUMAN_HIGH_VALUE_MODERN_EVENT_REPORTING',
            'historical_calibration': '2013_2024_AND_2026_DATED_POSITIVES',
            'highest_value_gap': 'co-located near-bottom DO+salinity+temperature and direct nearshore current'
        },
        {
            'cell': 'Mullet Point',
            'private_camera_metadata_passing_ids': mullet_cams,
            'independent_private_site_groups': mullet_groups,
            'public_candidates_not_production_evidence': public_candidates(reg, ['Mullet Point']),
            **common_missing,
            'current_transport': 'MODEL_OR_REGIONAL_PROXY_NOT_DIRECT_LOCAL',
            'water_level': 'BAY_MOUTH_OR_POINT_CLEAR_PROXY',
            'upstream_river_forcing': 'REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'MISSING_OR_UNVERIFIED',
            'same_day_social_reports': 'HUMAN_EXTERNAL_INTAKE',
            'historical_calibration': 'HISTORICAL_LITERATURE_CONTEXT_EXACT_ROWS_SPARSE',
            'highest_value_gap': 'dated historical-event recovery before dedicated hardware'
        },
        {
            'cell': 'Bay mouth/Dauphin Island',
            'private_camera_metadata_passing_ids': [],
            'independent_private_site_groups': [],
            'public_candidates_not_production_evidence': public_candidates(reg, ['Bay mouth context']),
            'direct_local_bottom_DO': 'HISTORICAL_DIRECT_AND_SOURCE_DEPENDENT_CURRENT',
            'direct_local_salinity_profile': 'HISTORICAL_DIRECT_AND_CURRENT_SOURCE_DEPENDENT',
            'direct_local_temperature_profile': 'DIRECT_OR_HISTORICAL_DIRECT',
            'direct_local_vertical_gradient': 'HISTORICAL_DIRECT',
            'current_transport': 'HISTORICAL_DIRECT_PLUS_MODEL',
            'water_level': 'NOAA_BAY_MOUTH_OBSERVATION_WHEN_AVAILABLE',
            'upstream_river_forcing': 'PROPAGATED_REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'NOT_PRIMARY_EVIDENCE_CLASS',
            'same_day_social_reports': 'LOWER_PRIORITY_HUMAN_CONTEXT',
            'historical_calibration': 'STRONG_SCIENTIFIC_HYDROGRAPHY_PLUME_RECORD',
            'verified_non_event_calibration': 'NOT_ESTABLISHED',
            'highest_value_gap': 'normalized profile/current ingestion with available-at timestamps'
        },
        {
            'cell': 'Shelf/FOCAL/West End CP',
            'private_camera_metadata_passing_ids': [],
            'independent_private_site_groups': [],
            'public_candidates_not_production_evidence': [],
            'direct_local_bottom_DO': 'HISTORICAL_OR_SEASONAL_DIRECT_SOURCE_DEPENDENT',
            'direct_local_salinity_profile': 'HISTORICAL_DIRECT',
            'direct_local_temperature_profile': 'DIRECT_OR_HISTORICAL_DIRECT',
            'direct_local_vertical_gradient': 'HISTORICAL_DIRECT',
            'current_transport': 'HISTORICAL_DIRECT_ADCP_HFR_PLUS_MODEL',
            'water_level': 'PROXY_OR_MODEL_BOUNDARY_CONTEXT',
            'upstream_river_forcing': 'PLUME_PROPAGATED_REGIONAL_PROXY_' + str(r.get('status', 'UNKNOWN')).upper(),
            'human_search_schema': 'NOT_APPLICABLE',
            'same_day_social_reports': 'NOT_PRIMARY_EVIDENCE_CLASS',
            'historical_calibration': 'STRONG_FOCAL_HFR_PLUME_SCIENTIFIC_DATASETS',
            'verified_non_event_calibration': 'NOT_ESTABLISHED',
            'highest_value_gap': 'normalized shelf-boundary time series from NCEI/GRIIDC/Hypoxia Watch'
        }
    ]

    voi = [
        {'rank': 1, 'gap': 'Direct near-bottom DO + salinity + temperature at Montrose/Daphne and Point Clear', 'expected_forecast_value': 'VERY_HIGH', 'cost': 'hardware/deployment'},
        {'rank': 2, 'gap': 'Historical event expansion plus observation-effort matched controls', 'expected_forecast_value': 'VERY_HIGH', 'cost': 'research/data engineering'},
        {'rank': 3, 'gap': 'Local shoreward transport/current measurement or validated high-resolution nowcast extraction', 'expected_forecast_value': 'HIGH', 'cost': 'moderate'},
        {'rank': 4, 'gap': 'Normalized ingest of in-bay CTD, Middle Bay, FOCAL/West End, Main Pass, HFR and Hypoxia Watch', 'expected_forecast_value': 'HIGH', 'cost': 'data engineering'},
        {'rank': 5, 'gap': 'Validated public-camera ROI/freshness plus prospective structured observations', 'expected_forecast_value': 'MODERATE_HIGH', 'cost': 'low_to_moderate'}
    ]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = {
        'generated_at_utc': now,
        'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
        'input_commit_sha': os.environ.get('GITHUB_SHA'),
        'camera_snapshot_main_commit': os.environ.get('CAMERA_SNAPSHOT_SHA'),
        'tests': t,
        'camera_metadata_status': c.get('status'),
        'private_metadata_pass': c.get('private_metadata_pass'),
        'expected_private_including_pending_onboarding': c.get('expected_private_cameras'),
        'passing_site_groups': c.get('passing_site_groups'),
        'new_montrose_camera_metadata_pass': any(x.get('camera_id') == 'montrose_shoreline' for x in passing),
        'river_status': r.get('status'),
        'river_rows': r.get('normalized_rows'),
        'river_parameter_counts': r.get('parameter_counts'),
        'river_distinct_series_including_gate_methods': len(r.get('series', [])),
        'desktop_modified_by_this_job': False,
        'google_device_inventory_accessed_by_this_job': False,
        'public_camera_pixels_captured_by_this_job': False,
        'chatgpt_automations_modified_by_this_job': False,
        'forecast_weights_changed': False,
        'private_media_uploaded_by_this_job': False,
        'raw_public_archive_path': 'model_data/public_archive',
        'water_quality_manifest_as_of': w.get('finished_at_utc'),
        'water_quality_status': w.get('status'),
        'water_quality_rows': w.get('normalized_rows'),
        'water_quality_unique_event_linked_rows': b.get('unique_event_linked_observations'),
        'water_quality_same_day_pairs_excluded': b.get('same_day_event_sample_pairs_excluded'),
        'water_quality_predictive_validity': 'NOT_ESTABLISHED',
        'private_camera_archive_note': 'Desktop acceptance previously verified R2 hashes/restore evidence; this cloud job does not independently re-authenticate private object storage.'
    }
    (HERE / 'upgrade_readiness.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (HERE / 'coverage_snapshot.json').write_text(json.dumps({
        'schema_version': '2.1',
        'generated_at_utc': now,
        'legend': ['DIRECT', 'PROXY', 'MODEL', 'HUMAN', 'MISSING'],
        'owner_camera_health_basis': c.get('status'),
        'cells': coverage,
        'value_of_information_rank': voi
    }, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

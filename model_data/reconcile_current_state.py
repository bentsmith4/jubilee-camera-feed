"""Rebuild state from one committed, validated evidence generation, without sensing.

No probability estimation or alert-policy inference. New event/critical-fault
assessments require review; they must not be silently suppressed by automation.
An already-assessed material input-quality fault is preserved while source rows
continue to reconcile; active direct-event evidence still requires review.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import bind_current_forecast as binding
import check_current_state_freshness as guard
import ingest_asos_weather as asos
import ingest_river_forcing as river
import desktop_acceptance as desktop

CAMERA = "bentsmith4/jubilee-camera-feed status.json, burst_status.json and vision.json"
MODEL = "NOAA NGOFS2 repository manifests"
ASOS = "NOAA/NWS ASOS KBFM and KMOB"
RIVER = "USGS NWIS lower-river forcing manifest"
WEEKS = "NOAA/NDBC Weeks Bay realtime"
ARCOS = "DISL ARCOS realtime hydrographic observations"
ARCOS_TEMPLATE = {
    "source": ARCOS,
    "station_location": "Named DISL ARCOS stations in and around Mobile Bay",
    "parameter": "dissolved oxygen, oxygen saturation, salinity, water temperature, turbidity and source depth field",
    "observed_vs_predicted_model": "DIRECT_STATION_OBSERVATION_ZERO_WEIGHT_PROXY",
    "units": "mg/L; % saturation; PSU; degC; FNU; m",
    "timezone_datum_depth": "UTC observations; sensor height above bed not established by public Grafana depth field",
    "shoreline_cell": "Mobile Bay regional loading/boundary context; station-specific",
    "independence_group": "disl_arcos_physical_stations"
}
CT = ZoneInfo("America/Chicago")


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


class CommittedReader(guard.Reader):
    """Never use a dirty checkout, downloaded artifact, or untracked source."""
    def __init__(self, root):
        super().__init__(root)
        self.commit = self.git("rev-parse", "HEAD").decode().strip()

    def read(self, path):
        guard.require((self.root / path).resolve().is_relative_to(self.root), "source path escapes repository")
        data = self.git("show", self.commit + ":" + path)
        self.hashes[path] = guard.digest(data)
        return data

    def blob(self, path):
        return self.git("rev-parse", self.commit + ":" + path).decode().strip()

    def exists(self, path):
        return bool(self.git("ls-tree", self.commit, "--", path).strip())


def build(root, now):
    guard.require(now.utcoffset() is not None, "issue time needs UTC offset")
    now = now.astimezone(timezone.utc)
    ct = now.astimezone(CT).isoformat()
    r = CommittedReader(root)
    prior_bytes = r.read(binding.SNAPSHOT)
    prior = json.loads(prior_bytes)
    binding.check(prior_bytes, r.json(binding.FORECAST))
    guard.require(guard.stamp(prior['snapshot_time_ct']) <= now, "issue time precedes prior state")
    limits = r.json("model_data/sensor_contract.json")["freshness_minutes"]
    # The existing ASOS and river consumers use these established limits.
    guard.require(limits['weather'] == asos.freshness_limit() and limits['regional_proxy'] == 180,
                  "Consumer freshness policy changed; review required")
    validated = {}
    for name in guard.PRODUCTS:
        validated[name] = (guard.camera_product(r, now) if name == "cameras"
                           else guard.environmental_product(name, r, now))
    s = copy.deepcopy(prior)
    by_source = {row['source']: row for row in prior['input_rows']}
    guard.require(len(by_source) == len(prior['input_rows']), "duplicate input source")

    def age(t):
        return round((now - guard.stamp(t)).total_seconds() / 60, 3)

    def row(source):
        fields = ('source', 'station_location', 'parameter', 'observed_vs_predicted_model',
                  'units', 'timezone_datum_depth', 'shoreline_cell', 'independence_group')
        if source == ARCOS and source not in by_source:
            return copy.deepcopy(ARCOS_TEMPLATE)
        return {k: copy.deepcopy(v) for k, v in by_source[source].items() if k in fields}

    def manifest(name):
        return r.json('model_data/' + name + '_manifest.json')

    def available(m):
        return m.get('retrieved_at_utc', m.get('retrieved_at', m.get('started_at_utc')))

    def context(source, m):
        return dict(row(source), evaluated_at_ct=ct,
                    retrieval_time_ct=guard.stamp(available(m)).astimezone(CT).isoformat(),
                    production_weight=0)

    # Explicit outages do not authorize reading retained normalized data.
    am = manifest('asos_weather')
    ar = r.json('model_data/asos_weather_normalized.json') if am['status'] == 'complete' else []
    if am['status'] == 'complete':
        raw_weather = json.loads(r.archive(am['raw_path'], am['raw_sha256']))
        reparsed, _ = asos.normalize(raw_weather, guard.stamp(available(am)), ar)
        guard.require(guard.semantic_rows(ar) == guard.semantic_rows(reparsed), 'ASOS archive/data mismatch')
        guard.require(len({(x['sensor_id'], x['parameter']) for x in ar}) == len(ar), 'ambiguous ASOS rows')
        for x in ar:
            binding.validate_weights(x)
            guard.require(x['value_status'] not in ('KNOWN', 'TRACE') or
                          x['qc_flag'] == 'LOCAL_CHECKS_PASS', 'ASOS admitted value has invalid QC')
    weather = asos.current_snapshot(ar, now, am['status'])
    weather_known = any(x['value_status'] in ('KNOWN', 'TRACE')
                        for st in weather['stations'].values() for x in st['parameters'].values())
    a = context(ASOS, am)
    a.update(parameter_admission=weather['stations'],
             admitted_status=('SOURCE_UNAVAILABLE' if am['status'] == 'unavailable' else
                              'ADMITTED_PARTIAL_FRESH_ASOS_REGIONAL_CONTEXT' if weather_known else 'UNKNOWN'),
             observation='Issue-time airport context only; blank, stale and rejected parameters remain UNKNOWN.')

    rm = manifest('river_forcing')
    rr = (river.normalize(json.loads(r.archive(rm['raw_path'], rm['raw_sha256'])),
                          guard.stamp(available(rm)), rm['source_url']) if rm['status'] == 'complete' else [])
    guard.require(all(guard.stamp(x['observed_at_utc']) <= now for x in rr), 'future river observation')
    series = river.summarize(rr, now)
    for x in series:
        latest = [z for z in rr if z['series_id'] == x['series_id'] and z['observed_at_utc'] == x['latest_at_utc']]
        known = x['fresh'] and all(z['research_qc_eligible'] for z in latest) and len({z['value'] for z in latest}) == 1
        x.update(value_status='KNOWN_UPSTREAM_PROXY' if known else 'UNKNOWN_STALE_OR_QC_REJECTED', production_weight=0)
        if not known:
            x['latest_value'] = None
    river_known = any(x['value_status'] == 'KNOWN_UPSTREAM_PROXY' for x in series)
    rv = context(RIVER, rm)
    rv.update(series=series, admitted_status=('SOURCE_UNAVAILABLE' if rm['status'] == 'unavailable' else
              'ADMITTED_FRESH_REGIONAL_UPSTREAM_PROXY' if river_known else 'UNKNOWN'),
              observation='Qualified upstream proxy only. No Bay-arrival assumption, edge extrapolation or additive gate-method double count.')

    wm = manifest('weeks_bay_realtime')
    wr = r.csv('model_data/weeks_bay_realtime_normalized.csv') if wm['status'] != 'unavailable' else []
    wa = []
    for station in ('WKQA1', 'WKXA1'):
        sr = [x for x in wr if x['station_id'] == station]
        if not sr:
            wa.append(dict(station_id=station, value=None, value_status='SOURCE_UNAVAILABLE', production_weight=0))
            continue
        tm = max(guard.stamp(x['observed_at']) for x in sr)
        limit = limits['weather'] if station == 'WKXA1' else limits['regional_proxy']
        for parameter in sorted({x['parameter'] for x in sr}):
            choices = [x for x in sr if guard.stamp(x['observed_at']) == tm and x['parameter'] == parameter]
            fresh = 0 <= age(tm.isoformat()) <= limit
            known = fresh and len(choices) == 1 and choices[0]['qc_status'] == 'NDBC_REALTIME_AUTOMATED_QC'
            known = known and choices[0]['value'] != '' and guard.stamp(choices[0]['available_at']) <= now
            value = float(choices[0]['value']) if known else None
            guard.require(value is None or math.isfinite(value), 'invalid Weeks Bay value')
            wa.append(dict(station_id=station, parameter=parameter, value=value,
                           unit=choices[0]['unit'] if choices else None, observed_at=tm.isoformat(),
                           value_status='KNOWN_REGIONAL_PROXY' if known else 'UNKNOWN_STALE' if not fresh else 'UNKNOWN_MISSING_OR_QC_REJECTED',
                           age_minutes=age(tm.isoformat()), freshness_minutes=limit, production_weight=0))
    wb = context(WEEKS, wm)
    wb.update(parameter_admission=wa, admitted_status=('SOURCE_UNAVAILABLE' if wm['status'] == 'unavailable' else
              'ADMITTED_PARTIAL_REGIONAL_CONTEXT' if any(x['value'] is not None for x in wa) else 'UNKNOWN'),
              observation='Latest station observations only; no missing-parameter backfill. Neither station measures Eastern Shore bottom oxygen.')

    xb = None
    if r.exists('model_data/arcos_realtime_manifest.json') and r.exists('model_data/arcos_realtime_sources.json'):
        xm = manifest('arcos_realtime')
        xr = r.csv('model_data/arcos_realtime_normalized.csv') if xm['status'] in ('complete', 'partial') else []
        xa = []
        configured = r.json('model_data/arcos_realtime_sources.json')['stations']
        from ingest_arcos_realtime import HYDRO_PARAMETERS, MET_PARAMETERS
        expected_parameters = {p[0] for p in HYDRO_PARAMETERS + MET_PARAMETERS}
        for station in configured:
            sr = [x for x in xr if x['station_id'] == station['station_id']]
            if not sr:
                xa.append(dict(station_id=station['station_id'], station_name=station['name'],
                               station_role=station['role'], value=None,
                               value_status='SOURCE_UNAVAILABLE_OR_NO_HYDRO', production_weight=0))
                continue
            for parameter in sorted(expected_parameters):
                pr = [x for x in sr if x['parameter'] == parameter]
                tm = max(guard.stamp(x['observed_at']) for x in (pr or sr))
                choices = [x for x in sr if guard.stamp(x['observed_at']) == tm and x['parameter'] == parameter]
                fresh = 0 <= age(tm.isoformat()) <= limits['arcos_realtime']
                qc = len(choices) == 1 and choices[0]['qc_status'] in ('ARCOS_RANGE_CHECK_PASS', 'SOURCE_QC_NOT_EXPOSED')
                known = fresh and qc and choices[0]['value'] != '' and guard.stamp(choices[0]['available_at']) <= now
                value = float(choices[0]['value']) if known else None
                guard.require(value is None or math.isfinite(value), 'invalid ARCOS value')
                xa.append(dict(
                    station_id=station['station_id'], station_name=station['name'],
                    station_role=station['role'], parameter=parameter, value=value,
                    unit=choices[0]['unit'] if choices else None, observed_at=tm.isoformat(),
                    value_status=('KNOWN_STATION_OBSERVATION_PROXY' if known else
                                  'UNKNOWN_STALE' if not fresh else 'UNKNOWN_MISSING_OR_QC_REJECTED'),
                    age_minutes=age(tm.isoformat()), freshness_minutes=limits['arcos_realtime'],
                    depth_geometry_status=(choices[0].get('depth_geometry_status') if choices else None),
                    is_direct_local_bottom_measurement=False, production_weight=0))
        xb = context(ARCOS, xm)
        xb.update(parameter_admission=xa,
                  admitted_status=('ADMITTED_PARTIAL_BAY_OXYGEN_CONTEXT'
                                   if any(x.get('value') is not None for x in xa) else 'UNKNOWN'),
                  observation='Direct observations at named ARCOS stations. They are zero-weight oxygen-loading/boundary context; public depth does not establish sonde height above bed or Point Clear/Montrose contact-strip bottom state.')
    

    mp = {}
    for name in guard.MODEL_PRODUCTS:
        m = manifest(name)
        p = dict(status=m['status'], retrieved_at_utc=available(m), retrieval_age_minutes=age(available(m)),
                 evidence_class='MODEL', production_weight=0, current_observed_transport_status='UNKNOWN_NOT_AN_OBSERVATION')
        if m['status'] == 'unavailable':
            p.update(admitted_status='UNKNOWN_UNAVAILABLE', availability_status='SOURCE_UNAVAILABLE',
                     error_type=m.get('error_type'), error=m.get('error'))
        else:
            data = r.csv('model_data/' + m.get('normalized_csv', m.get('normalized_data')))
            guard.require(all(float(x['production_weight']) == 0 for x in data), 'nonzero model weight')
            valid = [guard.stamp(x['valid_at']) for x in data]
            p.update(model_initialized_at_utc=max(guard.stamp(x['model_initialized_at']) for x in data).isoformat(),
                     valid_time_start_utc=min(valid).isoformat(), valid_time_end_utc=max(valid).isoformat(),
                     normalized_rows=len(data), admitted_status='ADMITTED_ANTECEDENT_MODEL_CONTEXT_ONLY' if name.endswith('nowcast') else
                     'ADMITTED_FORWARD_MODEL_GUIDANCE' if max(valid) >= now else 'UNKNOWN_NO_CURRENT_GUIDANCE')
            if name == 'ngofs2_point_clear_forecast' and max(valid) >= now:
                from ingest_ngofs2_point_clear import summarize_forward_transport
                ref = min(x for x in valid if x >= now)
                windows = summarize_forward_transport(data, ref)
                for h, w in windows.items():
                    w.update(start=ref.isoformat(), end=(ref + timedelta(hours=int(h))).isoformat())
                p.update(reference_valid_at_utc=ref.isoformat(), forward_transport_windows=windows)
            if name == 'ngofs2_shoreline_grid':
                p['sampling'] = [dict(cast=x['cast'], model_initialized_at=x['model_initialized_at'],
                      valid_times_utc=[z['valid_at'] for z in x['opened_slices']],
                      missing_lead_hours=[z['lead_hour'] for z in x['failed_slices']]) for x in m['casts']]
            p['coverage_caveat'] = 'Only published model locations, depths and valid times; missing slices remain UNKNOWN. No observed-current or skill claim.'
        mp[name] = p
    mr = row(MODEL)
    mr.update(products=mp, evaluated_at_ct=ct, production_weight=0,
              admitted_status='MODEL_CONTEXT_WITH_EXPLICIT_PRODUCT_GAPS',
              observation='Issue-relative summaries use validated committed rows; MODEL guidance is not an observation.')

    acceptance = desktop.consume(r, now, limits['camera'])
    status, vision = r.json('status.json'), r.json('vision.json')
    registry = r.json('model_data/camera_sources.json')
    cams, failed = [], []
    # `unclear` is a schema-defined ambiguity label, not a negative or an
    # event assessment.  It may pass only as unresolved visible context; the
    # builder never converts it into a non-event, probability, or alert change.
    quiet = (None, 'unknown', 'UNKNOWN', 'none', 'none_visible', 'unclear')
    for c in registry['cameras']:
        if c['access'] != 'owner_google':
            continue
        cid = c['camera_id']
        sc, v = status['cameras'][cid], vision['cameras'][cid]
        healthy = sc.get('ok') is True
        if not healthy:
            failed.append(cid)
        else:
            pixels = r.read(cid + '.jpg')
            guard.require(pixels.startswith(b'\xff\xd8') and pixels.endswith(b'\xff\xd9'), 'invalid camera JPEG: ' + cid)
            guard.require(v.get('burst_frame_count') == 3, 'invalid camera vision frame count: ' + cid)
        captured = sc.get('timestamp_ct') if healthy else None
        fresh = healthy and 0 <= age(captured) <= limits['camera']
        guard.require(all(v.get(k) in quiet for k in ('overall_jubilee_visual_signal', 'temporal_jubilee_signal')),
                      'REVIEW_REQUIRED: camera event assessment must not be silently changed')
        cams.append(dict(camera_id=cid, site_group=c.get('site_group'), shoreline_cell=c.get('shoreline_cell'),
                         captured_at_ct=captured, age_minutes=age(captured) if captured else None,
                         upstream_metadata_pass=healthy, admitted_status='ADMITTED_VISIBLE_SCOPE_CONTEXT' if fresh else 'UNKNOWN_STALE_OR_FAILED',
                         visibility=v.get('visibility', 'UNKNOWN') if fresh else 'UNKNOWN',
                         biological_detectability=v.get('detectability', 'UNKNOWN') if fresh else 'UNKNOWN',
                         overall_visual_signal=v.get('overall_jubilee_visual_signal', 'UNKNOWN') if fresh else 'UNKNOWN',
                         temporal_visual_signal=v.get('temporal_jubilee_signal', 'UNKNOWN') if fresh else 'UNKNOWN',
                         negative_event_label_allowed=False, raw_archive_verification=acceptance['status']))
    guard.require(len(cams) == 6, 'expected exactly six owner cameras')
    cross_camera = vision.get('cross_camera', {})
    guard.require(
        all(cross_camera.get(k) in quiet for k in
            ('overall_visual_jubilee_signal', 'montrose_visual_signal', 'point_clear_visual_signal'))
        and cross_camera.get('temporal_confirmation') in quiet + ('limited',),
        'REVIEW_REQUIRED: cross-camera event assessment')
    ca = row(CAMERA)
    ca.update(valid_time_ct=status['capture_time_ct'], evaluated_at_ct=ct,
              admitted_status='VISIBLE_SCOPE_CONTEXT_WITH_EXPLICIT_HEALTH_AND_AGE',
              observation='Committed vision classifications only. Unknown or absent visible signals do not establish biological absence or dawn acceptance.',
              camera_health=dict(expected_private_cameras=6, private_metadata_pass=6-len(failed),
                                 private_cameras=cams, unknown_upstream_camera_ids=failed))
    old_fault = prior.get('operational_fault_assessment', {})
    preserved_material_fault = prior['alert_gates']['material_critical_input_fault']
    camera_failure_set_changed = sorted(failed) != sorted(old_fault.get('failed_camera_ids', []))
    guard.require(not camera_failure_set_changed or preserved_material_fault,
                  'REVIEW_REQUIRED: changed camera failures need material-fault assessment')
    prior_weather = by_source[ASOS]['parameter_admission']
    old_weather_known = any(x['value_status'] in ('KNOWN', 'TRACE') for station, v in prior_weather.items()
                            for x in binding.asos_parameters(station, v).values())
    old_river_known = any(x['fresh'] and x['value_status'].startswith('KNOWN') for x in by_source[RIVER]['series'])
    # If a material input-quality fault is already explicitly assessed and active,
    # continue reconciling newer UNKNOWN source state instead of freezing the
    # canonical pair. This preserves the alert gate and does not infer recovery.
    guard.require(not (old_weather_known or old_river_known) or weather_known or river_known or preserved_material_fault,
                  'REVIEW_REQUIRED: simultaneous weather/river loss needs material-fault assessment')
    guard.require(not prior['alert_gates']['direct_event_evidence_present'],
                  'REVIEW_REQUIRED: retain active assessed event until explicit review')
    # Unsupported manual inputs are preserved as dated evidence, never relabeled current.
    replacements = {CAMERA: ca, MODEL: mr, ASOS: a, RIVER: rv, WEEKS: wb}
    if xb is not None:
        replacements[ARCOS] = xb
    s['input_rows'] = [replacements.get(x['source'], dict(source=x['source'], admitted_status='UNKNOWN_NOT_REASSESSED',
                        historical_context=copy.deepcopy(x.get('historical_context', x)),
                        historical_snapshot_time_ct=x.get('historical_snapshot_time_ct', prior['snapshot_time_ct'])))
                       for x in prior['input_rows']]
    if xb is not None and ARCOS not in by_source:
        s['input_rows'].append(xb)
    static_unknowns = [
        'Direct local bottom/contact-strip oxygen, salinity/temperature profiles and stratification remain UNKNOWN.',
        'Observed local water level/currents and shoreline wind/rain remain UNKNOWN; model guidance and regional proxies are not local observations.',
        'River-to-Bay travel time remains uncalibrated.',
        'Out-of-view biology and full-cell non-events remain UNKNOWN; no new public-player or human-report search is claimed.',
        'Missing model slices and stale, missing or QC-rejected observations remain UNKNOWN; see per-source admission.',
    ]
    unavailable = [name for name, p in validated.items() if not p['admissible']]
    s['known_unknowns'] = static_unknowns + [name + ': SOURCE_UNAVAILABLE/UNKNOWN' for name in unavailable]
    s['active_faults'] = copy.deepcopy(s['known_unknowns'])
    s['rejected_or_unknown_inputs'] = [dict(source=n, status='SOURCE_UNAVAILABLE', value_status='UNKNOWN') for n in unavailable]
    s.update(snapshot_time_ct=ct, principal_dawn_visual_assessment_status='NOT_PERFORMED_BY_POST_PUBLICATION_RECONCILIATION',
             change_summary='Rebuilt issue-time context from one committed evidence generation; retained assessed dated outlooks and alert gates.',
             notification_reason='Existing four-trigger alert contract retained; no new event or critical-fault inference.',
             material_change_since_prior_snapshot=True,
             forecast_opportunity_status='Existing dated heuristic outlooks retained without numerical or horizon change; not a new calibrated forecast.')
    s.pop('dawn_ct', None)
    s.pop('weather_input_readback', None)
    s['probability_basis']['reassessment_method'] = 'Committed-evidence issue-time admission; frozen dated heuristic outlooks and zero production weights retained. No automatic event/fault policy inference.'
    s['probability_basis'].pop('summary', None)
    s['operational_fault_assessment'] = dict(active_fault_present=bool(failed) or preserved_material_fault, failed_camera_ids=failed,
        assessed_material_critical_input_fault_preserved=preserved_material_fault,
        camera_failure_set_changed_under_preserved_material_fault=bool(camera_failure_set_changed and preserved_material_fault),
        new_fault_notification_required=False, recovery_notification_required=False,
        prior_recovery_context=(dict(snapshot_time_ct=prior['snapshot_time_ct'], recovery_notification_required=True)
                                if old_fault.get('recovery_notification_required') else old_fault.get('prior_recovery_context')),
        all_six_desktop_archive_acceptance=acceptance['status'], desktop_acceptance_receipt=acceptance,
        existing_material_input_quality_alert_policy_changed=False,
        basis='No new assessed critical fault or recovery notification is inferred by this builder. Any previously assessed material input-quality fault is preserved unchanged while current source rows continue to reconcile.')
    # Include executable/admission contracts, but exclude prior output bytes from dedup identity.
    for path in ('model_data/model_policy.md', 'model_data/operations_contract.json',
                 'model_data/reconcile_current_state.py', 'model_data/desktop_acceptance.py', 'model_data/bind_current_forecast.py',
                 'model_data/check_current_state_freshness.py', 'model_data/ingest_asos_weather.py',
                 'model_data/ingest_river_forcing.py', 'model_data/ingest_weeks_bay_realtime.py',
                 'model_data/ingest_ngofs2_point_clear.py'):
        r.read(path)
    for path in ('model_data/ingest_arcos_realtime.py', 'model_data/arcos_realtime_sources.json'):
        if r.exists(path):
            r.read(path)
    hashes = {p: h for p, h in r.hashes.items() if p not in (binding.SNAPSHOT, binding.FORECAST)}
    admission = [weather['stations'][st]['status'] for st in sorted(weather['stations'])]
    admission += [x['value_status'] for st in weather['stations'].values() for x in st['parameters'].values()]
    admission += [x['value_status'] for x in series + wa] + [x['admitted_status'] for x in cams] + [p['admitted_status'] for p in mp.values()]
    if xb is not None:
        admission += [x['value_status'] for x in xa]
    admission += [acceptance['status'], acceptance['reason_codes']]
    identity = guard.digest(guard.canonical([hashes, admission]).encode())
    if prior['reconciliation'].get('consumption_identity') == identity:
        return None
    s['reconciliation'] = dict(as_of_utc=now.isoformat(), input_commit_sha=r.commit,
        prior_snapshot_time_ct=prior['snapshot_time_ct'], prior_snapshot_blob=r.blob(binding.SNAPSHOT),
        alert_threshold_percent=20, alert_comparator='>', forecast_weights_changed=False,
        consumption_identity=identity,
        scope='Committed evidence only; bounded desktop receipts are operational context. No new capture, retrieval, calibration, public/human observation or desktop/dawn acceptance.',
        source_provenance={p: dict(sha256=h, git_blob=r.blob(p)) for p, h in hashes.items()},
        validation_summary={n: dict(status='VALIDATED_PUBLISHED_CONTEXT' if p['admissible'] else 'SOURCE_UNAVAILABLE',
             available_at_utc=p['available_at'].isoformat(), fingerprint=p['fingerprint']) for n, p in validated.items()})
    raw = encode(s)
    forecast = binding.project(raw)
    guard.require(s['outlook'] == prior['outlook'] and s['alert_gates'] == prior['alert_gates'], 'assessed outlook/gates changed')
    guard.require(forecast['outlooks'] == json.loads(r.read(binding.FORECAST))['outlooks'], 'forecast outlooks changed')
    return raw, encode(forecast)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--as-of')
    args = parser.parse_args()
    result = build(args.root, guard.stamp(args.as_of) if args.as_of else datetime.now(timezone.utc))
    if result is None:
        print('UNCHANGED: committed inputs and admission state already consumed')
        return
    # Publication is atomic at the Git commit boundary; these are isolated candidate files.
    for path, data in zip((binding.SNAPSHOT, binding.FORECAST), result):
        (args.root / path).write_bytes(data)
    binding.run(args.root, check_only=True)
    report = guard.inspect(args.root, guard.stamp(json.loads(result[0])['snapshot_time_ct']))
    guard.require(report['status'] == 'CURRENT', 'rebuilt state failed freshness: ' + guard.canonical(report))
    print('PASS: candidate pair bound to validated committed evidence')


if __name__ == '__main__':
    main()

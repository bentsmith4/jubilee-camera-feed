# October 24 NGOFS2 material-fault recovery review

Existing ownership: J01 Sensing & Alerting; J11 consumes the bound pair; Jubilee Dot coordinates through MODEL_WORK_REGISTER.md.

## Decision

RECOVERED_NGOFS2_FORECAST_VALIDATION_INCIDENT. Clear only the October 22 03Z forecast-validation incident through an explicit dated review. Do not change executable code or automatic latch behavior. PR #132 was already merged and only recorded the October 24 Dawn horizon; no later recovery review or competing recovery PR was present at inspection.

## Failed versus recovered evidence

The prior fault originated on **October 22**, not October 24. Workflow 39734344678 jobs 119676441726 (attempt 1) and 119678512221 (attempt 2) each logged `Station embedded valid times disagree with cycle/cast or six-minute coverage` for the forecast collectors. The persisted older October 21 21Z complete manifests were retained fallback context, not proof those rejected 03Z files passed. Original rejected NetCDF bytes / exact offending times were not retained in reviewed evidence; the precise original defect remains unverified. No historical error is rewritten or reclassified as an outage.

Both October 24 09Z forecast manifests report complete HTTPS station ingestion, embedded-time PASS and the same full-file SHA-256 a4ea05fd3d23e72b6c61e21d7d95e5a1d754607e195e2443cd1a5862984f00d2 (116,012,123 bytes). They are two extracts of one NOAA file, not independent sources. S3 returned 404; same-cycle THREDDS succeeded. No newer-cycle failure is listed in those manifests. This review reuses committed evidence without downloading another station file or claiming a new live NOAA check.

Independent offline checks verified decompressed archive hashes, exact archive/CSV consistency through the existing reconciler, finite MODEL values, zero weights, initialization/availability ordering, row counts, and all series' exact 481 six-minute valid times from October 24 09:00 UTC through October 26 09:00 UTC. Point Clear: 5,291 rows = 11 complete series. Named Mobile Bay: 21,645 rows = 45 complete series across all five configured targets, with no unresolved targets. Existing proxy-distance caveats remain. The current issue time falls within coverage; the unchanged issue-relative transport calculation has complete 1/3/6/12-hour windows. Retrieval age is recorded below; forecasts are evaluated against valid-time coverage under the existing consumer contract, not incorrectly subjected to observation-age limits.

## Narrow recovery criteria and residual limitations

The October 12 recovery review concerned recurrent camera acquisition failures and required repeated fresh camera cycles. It is not a generic requirement that prevents closing a later, separate model-validation incident. The October 22 reviewed basis explicitly left only this NGOFS2 incident active after camera recovery. Current camera metadata reports no acquisition failures; the 60-minute expiry rule still marks older observations UNKNOWN. Reconciliation preserves all per-source expiry/QC and remaining scientific gaps. Twenty qualified upstream river series are fresh at the review; source uncertainty, missing model slices, stale regional observations and unverified full desktop/archive acceptance are not silently cleared.

Recovery establishes valid newer guidance availability, not repair of the old 03Z bytes, immunity to recurrence, observed current, event confirmation or forecasting skill. The unchanged reconciler still preserves future assessed faults until explicit review.

## Notification disposition

The material fault gate, active-fault flag and stale October 22 reason are reconciled together. All four existing event/probability/fault triggers are false, so notification_condition_met=false and notification_suppressed=true. A dated recovery record with one incident identity records the transition separately; recovery_notification_required is a reporting handoff, not proof of delivery. No recovery alert was sent, no schedule was created, and no delivery claim is made. Existing permitted reporting must respect 21:00 America/Chicago, recheck current conditions, and suppress repeated messages for this incident. The normal reconciler preserves this review and rolls the transition flag into prior_recovery_context rather than repeatedly asserting a new recovery.

Probabilities, confidence, dates/horizon, zero production weights, UNKNOWN semantics, camera coverage/schedules, thresholds, strict >20% comparator and 9 p.m. restriction are unchanged. Historical recoveries remain intact.

## Evidence receipt

```json
{
  "schema_version": "1.0",
  "decision": "RECOVERED_NGOFS2_FORECAST_VALIDATION_INCIDENT",
  "assessed_at_utc": "2026-10-24T16:01:44.683862+00:00",
  "reviewed_main_commit_sha": "af3d725065de52d6a5796b1dc8abf5df5cee74da",
  "assessment_document": "model_data/MATERIAL_FAULT_RECOVERY_20261024.md",
  "scope": "One-time review of October 22 03Z forecast validation incident; not automatic future clearance or proof the rejected bytes were repaired.",
  "original_workflow_run_id": 39734344678,
  "original_attempt_job_ids": [
    119676441726,
    119678512221
  ],
  "recovered_products": {
    "ngofs2_point_clear_forecast": {
      "rows": 5291,
      "series": 11,
      "points_per_series": 481,
      "start": "2026-10-24T09:00:00+00:00",
      "end": "2026-10-26T09:00:00+00:00",
      "subset_sha256": "487cfcd51a38f544bf271ea1cc4682d0b5738cfed09d1baeb789c3913bf5c488",
      "source_sha256": "a4ea05fd3d23e72b6c61e21d7d95e5a1d754607e195e2443cd1a5862984f00d2",
      "retrieved_at": "2026-10-24T11:33:46.653750+00:00",
      "unresolved_targets": [],
      "retrieval_age_minutes_at_review": 267.967
    },
    "ngofs2_mobile_bay_named_stations_forecast": {
      "rows": 21645,
      "series": 45,
      "points_per_series": 481,
      "start": "2026-10-24T09:00:00+00:00",
      "end": "2026-10-26T09:00:00+00:00",
      "subset_sha256": "ac3ae24ac17c258f6ad23faaded193deed5388b259c238dbe85aaf248ee7fba4",
      "source_sha256": "a4ea05fd3d23e72b6c61e21d7d95e5a1d754607e195e2443cd1a5862984f00d2",
      "retrieved_at": "2026-10-24T11:33:51.531203+00:00",
      "unresolved_targets": [],
      "retrieval_age_minutes_at_review": 267.886
    }
  },
  "criteria": {
    "archived_subset_hashes_and_normalized_rows_match": true,
    "producer_embedded_time_validation_pass": true,
    "all_series_have_481_exact_six_minute_timestamps": true,
    "all_five_named_targets_resolved": true,
    "current_issue_time_and_full_12h_forward_window_covered": true,
    "production_weights_zero": true,
    "no_current_camera_acquisition_failures": true,
    "fresh_qualified_upstream_river_series": 20
  },
  "historical_failure_limit": "Rejected original NetCDF bytes and exact offending timestamps were not retained in the reviewed evidence. Logs prove validation failed twice; root cause and repair of those original bytes are unverified.",
  "notification": {
    "event_id": "J01-NGOFS2-20261022T030000Z-recovery-20261024",
    "delivery_status": "NOT_SENT",
    "disposition": "Record once in existing permitted reporting after 21:00 America/Chicago; suppress duplicate recovery notices by this incident identity. Recheck current operational state before reporting.",
    "new_alert_or_schedule_created": false
  },
  "remaining_limitations": "Expected camera expiry remains UNKNOWN; direct shoreline oxygen/currents and missing model slices remain UNKNOWN. Desktop/archive acceptance and notification delivery remain unverified. No predictive-skill claim.",
  "future_scope": "Future validation failures require explicit review under unchanged fail-closed guards."
}
```

# October 12 camera freshness and critical-fault recovery review

Existing ownership: J01/J06/J13, Jubilee Sensing & Alerting; Jubilee Dot coordinates through MODEL_WORK_REGISTER.md. No new process.

## Finding

The 21:49:28 CDT snapshot (`36b3d2cb4d05`) correctly expired all six camera observations: ages 99.942–103.008 minutes exceed the unchanged 60-minute limit. This was an expected interval in canonical sampling, not a missed 21:06 capture or six acquisition failures. The material gate did not originate from that expiry.

Read-only PointClearPC verification at approximately 22:49 CDT found Jubilee Live Cameras Running, with live_loop.py calling capture_service.main; Dawn Cameras and Unattended Test were Disabled. Installed capture_service.py SHA256 `2598aa3eb1e2c6f52a6c6d1afed52b8b5e781fbc112ec545c1bf150e5281a464` matches the repository. Its overnight baseline hours are 00, 02, 04, 20 and 22 at :06, with dawn-window overrides unchanged. Thus 21:06 is deliberately absent. Near-live acquisition is a separate product and does not make old canonical vision observations fresh.

The service log records normal pipeline completion at 20:11:05 and 22:11:12; the state records the 22:06 slot, last canonical success 22:11:12 and advancing heartbeat 22:49:42. The state's retained canonical_failures=1 is not evidence of a current failure: code resets the internal counter on success but does not reset that historical state field. It is not used to justify this recovery. No scheduler or runtime edit was made.

## Fault provenance and operational categories

| Category | Verified evidence | Determination |
|---|---|---|
| Original October 1 freshness fault | PR #66 merge `f5e36ff9fce4528d1eb74c782d07e13049d62701` explicitly cleared it October 5, 14:17 CDT | Clearance survived reconciliation; it was not accidentally resurrected. |
| Subsequent genuine acquisition fault | `bccb0b668a67cb2e92b8c4a637e802bb18a2ac7d`, October 5 22:25:58 assessment, sets false→true after E2 back-deck and E3 bay-mouth failures | Genuine Point Clear coverage loss, 1/3 views left. Full first-parent snapshot history through reviewed main contains no later true→false transition. See MATERIAL_FAULT_LATCH_TRACE_20261006.md. |
| October 12 recurrence | 18:06 commit `a572d6b4ce76ee7ec63918b0256562d909c801ea` and 19:06 `7a2f6d1561807086cdcd5a2ea2d6a6789355fb7b` both have those two cameras failed | Operational concern remained real that evening. A successful pipeline exit alone does not mean every camera succeeded. Root cause remains unresolved. |
| Repeated recovery | 20:06 commit `a869ef5b6067f1ebe1070a1f25c2d12bbc3fb68a`, 22:06 `b6f2665abc86d26c46badcc8b13af38f4f390300` | Both have six healthy cameras, three frames each, matching status/burst/vision cycle identity and successful analysis rows. |
| 21:49 observation expiration | `36b3d2cb4d05`, all six UNKNOWN_STALE_OR_FAILED, no failed IDs | Expected between scheduled bursts. Keep UNKNOWN; no evidence of a missed scheduled capture. |
| Preserved alert | Reconciler copies the previously assessed gate and requires explicit recovery review | An uncleared subsequent operational fault, not an inferred new equipment fault. Historical October 5 original-fault recovery is not authority to clear it. |

## Notification judgment

The material-fault trigger was justified by actual recurrent camera coverage loss. At 21:49 it was mechanically correct under the existing explicit-review latch contract, but must not be described as a newly detected six-camera failure. `notification_condition_met=true` is eligibility under the four-trigger OR, not proof of delivery. `new_fault_notification_required=false` says this builder inferred no new incident; it does not clear the prior incident. A new alert solely because the expected inter-burst observations expired would not be justified. Actual message delivery is not established by these JSON fields.

At the time of that stale snapshot a clearance based on fresh six-camera evidence was not supported. The later 22:06 burst permits the explicit, dated recovery below. This is prospective recovery, not backdated rewriting of the 21:49 record.

## Smallest safe correction

Perform one explicit recovery assessment and atomically bind the snapshot/forecast pair, following the existing October 5 recovery workflow. No executable code or automatic clearing rule changes. Preserve the earlier recovery record; add a separately dated review for this subsequent fault. Preserve all per-source UNKNOWN handling, all six cameras, 60/90/180-minute freshness limits, schedules, probabilities, confidence, weights, thresholds, strict >20% comparator, forecast dates and 9 p.m. gate.

Current committed evidence is replayed through reconcile_current_state.py (archive/hash/provenance and issue-time admission), then recovery requires six fresh healthy cameras, both QC-admitted ASOS winds, 20/20 fresh qualified river series, repeated healthy canonical cycles and no active event/probability trigger. NGOFS2 DAP outages remain real SOURCE_UNAVAILABLE/UNKNOWN; scientific gaps and stale ARCOS context remain UNKNOWN. These zero-weight residual sources do not independently sustain the assessed Point Clear camera-coverage incident; no probability or event claim relies on them. Current archive acceptance stays NOT_VERIFIED.

The recovery is bounded: recurrent hardware/network/capture failure remains possible. New camera failures still fail closed for materiality review; the reconciler still cannot automatically clear a future assessed fault. Expected overnight expiry is not proof of equipment failure or a biological non-event.

## Validation and coordination

Exact assessment evidence is embedded below and in the snapshot's material_fault_recovery_review_20261012. Existing binding, strict Dawn horizon and current-state provenance/freshness validation pass. Relevant regression results and merge receipt are recorded in the PR. No extra capture, paid inference, notification, task or scheduler was started.

Jubilee Dot: consume this under existing J01/J06/J13; distinguish recovered current incident from unresolved intermittent E2/E3 cause and notification-delivery acceptance. Do not repeat this recovery or alter cadence to remove expected UNKNOWN intervals. Repository handoff is delivered with the existing register; native Dot acknowledgment remains pending and is not implied by this document.

```json
{
  "schema_version": "1.0",
  "decision": "RECOVERED_RECURRENT_POINT_CLEAR_CAMERA_COVERAGE_FAULT",
  "assessed_at_utc": "2026-10-13T03:51:33.537332+00:00",
  "reviewed_main_commit_sha": "c1b6887e98c4bd5b924292b3e02fe5ab18ad0ac4",
  "activation_commit": "bccb0b668a67cb2e92b8c4a637e802bb18a2ac7d",
  "assessment_document": "model_data/MATERIAL_FAULT_RECOVERY_20261012.md",
  "scope": "Explicit one-time recovery review of subsequent October 5 Point Clear coverage fault and October 12 recurrence; not automatic future clearance.",
  "repeated_healthy_cycles": [
    {
      "commit": "a869ef5b6067f1ebe1070a1f25c2d12bbc3fb68a",
      "capture_time_ct": "2026-10-12T20:06:02.970890-05:00",
      "healthy_cameras": 6,
      "frames": 18
    },
    {
      "commit": "b6f2665abc86d26c46badcc8b13af38f4f390300",
      "capture_time_ct": "2026-10-12T22:06:33.472943-05:00",
      "healthy_cameras": 6,
      "frames": 18
    }
  ],
  "camera_ages_minutes": {
    "montrose_pier_boat": 44.586,
    "montrose_pier_bird": 41.899,
    "montrose_shoreline": 42.984,
    "pcl_e2_back_deck": 43.922,
    "pcl_e2_bay_mouth": 43.47,
    "pcl_e3_bay_mouth": 42.349
  },
  "asos_wind_ages_minutes": {
    "KBFM": 58.559,
    "KMOB": 55.559
  },
  "fresh_qualified_river_series": 20,
  "river_age_range_minutes": [
    51.56,
    81.56
  ],
  "remaining_limitations": "Intermittent E2/E3 failure cause, notification delivery and current full desktop/archive acceptance remain unverified. NGOFS2 outages and scientific gaps remain UNKNOWN; no event or predictive-skill claim.",
  "future_scope": "New acquisition degradation requires explicit review under existing guards; expected camera expiry remains UNKNOWN, never equipment-failure proof."
}
```

# Production failure fixture

These files are byte-for-byte copies from commit
`845eecd6ad019341730581496bfea9353618ae68` in
`bentsmith4/jubilee-camera-feed`, the 2026-09-28 00:16 CT publication.

- `current_state_snapshot_20260928T0016.json` SHA-256:
  `c9288fb907e45f9a3ceb28504bdd1de059749cff2d5cf68ff079349e55bc335e`
- `current_forecast_20260928T0016.json` SHA-256:
  `6efdddf9f2b537d4e52c1121b2019c1322b3c5254bcd7bae6ea2834e38b3c2dc`

Source failure: https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36381503096

The hash binding was correct, but the snapshot's prose `probability_basis`
violated the binder contract. Once explicitly repaired, the full fixture also
exercises the production ASOS `status`/`parameters` envelope, stale weather,
partial river coverage, six cameras, unavailable model guidance and the existing
material-input-fault notification gate. These files are historical test data,
not current sensing products. Do not normalize away the original failure.


## 00:34 CT recovery-with-no-trigger fixture

`recovery_no_forecast_trigger_20260928T0034.json` preserves the production-shaped
operational recovery context from the September 28 00:34 CT snapshot after
forecast-notification alignment. All four authoritative forecast triggers are
false, `notification_condition_met=false`, and
`notification_suppressed=true`, while
`operational_fault_assessment.recovery_notification_required=true` remains
recorded as operational context. The regression verifies that recovery alone
does not bypass the existing four-trigger forecast contract.

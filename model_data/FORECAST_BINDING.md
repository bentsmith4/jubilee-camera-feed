# Current-state / forecast publication

`current_forecast.json` is a frozen heuristic projection of the already-assessed
`current_state_snapshot.json`. It is not a calibrated model run or a new sensing
cycle. Its issue time is the snapshot assessment time, not the repair time.

## Writer schema contract

The cloud **Jubilee Sensing & Alerting** task owns current-state synthesis; the
repository camera and environmental producers do not write this snapshot.
Every writer, including a Dawn Brief that updates the pair, must preserve
`probability_basis` as an object with these required fields:

```json
{
  "probability_type": "HEURISTIC_JUDGMENT_NOT_EMPIRICALLY_CALIBRATED",
  "numeric_change_from_prior_snapshot": 0,
  "reassessment_method": "The actual supported reassessment method",
  "summary": "Optional explanatory prose"
}
```

The zero must be a JSON number, never a boolean or string, and must be supported
by the assessment. A nonzero change requires separate reassessment. The method
must be a nonempty string. Never replace the object with narrative text or infer
the missing attestations from that text. Additional explanatory fields are
preserved. Malformed JSON/schema is a publication defect, not a missing sensor
reading; it must fail visibly rather than be converted to UNKNOWN.

ASOS `parameter_admission` accepts the existing flat station-to-parameter map
and the production station envelope `{ "status": ..., "parameters": {...} }`.
The envelope must contain exactly those two fields, a nonempty parameter map,
recognized per-field admission statuses, and a station status consistent with
its parameters. `PARTIAL_FRESH` retains the same partial-admission coverage;
it is not permission to re-admit stale source values. `UNKNOWN_STALE` requires
explicit
`STALE_AT_ISSUE_TIME` reasons. Coverage uses admitted `value_status`, never the
historical `source_value_status` or stale `source_value`. All detailed UNKNOWN
reasons and source values remain in the snapshot; no weather is promoted.

After updating a snapshot, run from the repository root:

```sh
python model_data/bind_current_forecast.py
python model_data/bind_current_forecast.py --check
git add model_data/current_state_snapshot.json model_data/current_forecast.json
```

Commit the pair together. Repeat the check after rebasing onto concurrent
updates, before pushing. The binding command refuses to replace different
outlooks: changes to assessed ranges/dates/central estimates/confidence require
explicit forecast reassessment first. Nonzero new input weights or a changed
threshold also require separate model review.

The SHA-256 is over the **exact snapshot bytes**, so a correction with the same
timestamp still needs rebinding. `input_commit_sha` retains its original meaning:
the snapshot's `reconciliation.input_commit_sha` (the upstream evidence commit),
not the later commit publishing the snapshot or forecast. UNKNOWN text, coverage,
assessed outlooks, and gates come from the snapshot; missing measurements are
never filled with zero. Opportunity gates retain the existing central-estimate
basis and strict `>20` comparator.

Jubilee Forecast Consistency runs the read-only check on pull requests and main
pushes touching either file, the binding code, its tests, or its workflow. It
fails visibly on a snapshot-only update, including same-timestamp byte changes,
or stale/mutated forecast fields. It does not send Jubilee alerts, change branch
protection, write forecasts automatically, or gate independent sensor producers.
It validates the published pair, not the scientific freshness of the original
assessment, desktop acceptance, or next-dawn execution.

## September 28 schema repair

Commit `cc774eb343ac3977df4bbb4e232ee51c04a7621c` first replaced the basis
object with prose and introduced the ASOS station envelope. Commit
`845eecd6ad019341730581496bfea9353618ae68` repeated that shape in its 00:16 CT
publication. Run `36381503096` passed synthetic fixtures but failed on the live
pair. Both publications came through cloud synthesis; no repository production
script contains another snapshot writer. The saved sensing instructions lacked
the binding/schema publication requirement.

The repair restores only the snapshot's basis object, retains the original
prose as `summary`, and uses the existing forecast's unchanged method and type.
The frozen ranges and central estimates support the explicit numeric-zero
attestation. Rebinding restores canonical forecast metadata: the exact hash,
ASOS coverage summary, dated-window scope wording and pending-verification text.
The window scope was explicitly reconciled before binding; the binder's refusal
to overwrite different outlooks remains intact. Issue time, evidence commit,
probabilities, confidence, UNKNOWN evidence, weights and all gates are unchanged.
This is not a fresh assessment using subsequent source publications.

The exact failing pair is retained in `tests/fixtures/forecast_binding/` with
provenance in its README. Regressions require the broken snapshot to fail
read-only in both CLI modes, then exercise the explicitly repaired full
production shape. Future publishers must run the binder and its check before
committing the pair and verify readback. An unavailable execution path is an
explicit publication-verification blocker, never a claimed passing check.

### Concurrent 00:34 CT recovery: forecast contract resolution

Before the schema repair could merge, main advanced to
`2d9c17f01abb83e16294be1696d853f66109ae18`. The repair preserves that newer
snapshot's source admissions, UNKNOWNs, probabilities and timestamps while
restoring the structured basis and canonical forecast metadata.

The 00:34 CT snapshot also recorded an operational recovery:
`operational_fault_assessment.recovery_notification_required=true`. A repository
policy search found no authoritative rule that makes recovery a fifth forecast
alert trigger. `operations_contract.json` and `model_policy.md` do not define
one, and the binding contract remains the OR of the two strict >20% opportunity
gates, direct-event evidence, and material-critical-input fault.

Accordingly, recovery remains operational context, not a forecast notification
condition. The snapshot now has `notification_condition_met=false` and
`notification_suppressed=true` when all four forecast triggers are false.
The operational recovery flag and basis remain intact. This does not change
probability ranges, UNKNOWN semantics, source observations, production weights,
or the strict `>20%` threshold. Validation remains strict: any future snapshot
that marks a forecast notification true without one of the four explicit
triggers still fails with `Snapshot notification gates disagree`.

A production-shaped recovery-with-no-trigger regression captures the 00:34 CT
operational context and verifies that the binder projects no forecast
notification while preserving the recovery assessment.


## Dawn horizon maintenance

The ordinary sensing reconciler may preserve an older reviewed outlook while it
updates source state; it does not own forecast-horizon maintenance. Before a
Jubilee Dawn Forecast publishes numerical ranges, the post-dawn layer must
require exactly three America/Chicago dates: the snapshot issue date, issue
date + 1, and issue date + 2.

A narrow reviewed zero-change maintenance path is provided for the case in
which the existing three dated heuristic rows have identical Point Clear and
Daphne/May Day ranges, central estimates and confidence. It may move those
three identical rows onto the current three-day horizon without changing any
number, weight, alert threshold, UNKNOWN input or evidence classification:

```sh
python -B model_data/roll_forward_dawn_outlook.py --as-of <offset-aware-time>
python -B model_data/bind_current_forecast.py --check --require-dawn-horizon
```

If the source horizon is not exactly three consecutive days, the three daily
profiles differ, the snapshot is not from the current Central date, the run is
outside May 18-November 14, or any binding/policy invariant fails, the
roll-forward stops with `REVIEW_REQUIRED`. Numerical reassessment remains a
separate Dawn Forecast/model-governance action; sensing and Dawn Timing do not
inherit it.

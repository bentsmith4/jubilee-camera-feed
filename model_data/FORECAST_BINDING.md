# Current-state / forecast publication

`current_forecast.json` is a frozen heuristic projection of the already-assessed
`current_state_snapshot.json`. It is not a calibrated model run or a new sensing
cycle. Its issue time is the snapshot assessment time, not the repair time.

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

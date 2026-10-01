# Current-state source freshness

`python -B model_data/check_current_state_freshness.py` reads the checkout and
prints JSON; it exits 1 for `STALE` or `ERROR`. It does not write any file, fetch
data, capture cameras, run a forecast, promote evidence, rebind a forecast, send
an event alert, or change UNKNOWN values. `--as-of <offset-aware time>` supports
offline replay. Use a full-history checkout: baseline source objects come from
the snapshot's SHA-256/blob provenance, with its explicit `input_commit_sha` as
the fallback for unlisted companion files. Missing history fails visibly.

## Policy

This adds a **30-minute maximum reconciliation lag** for the current-state
label. It does not change the existing 60/90/180-minute sensor freshness limits.
If a materially different admissible product exists, a snapshot no more than
30 minutes old is `PENDING_RECONCILIATION`; an older snapshot is `STALE`.
The clock starts at the snapshot issue time, not the latest producer refresh.
Thus repeated refreshes cannot continually reset the grace period. Both the
snapshot age and each product's source-to-snapshot time gap are reported.
An unchanged snapshot does not fail from wall-clock age alone in this narrow
guard; source health and forecast validity remain separate checks.

Admissibility is evaluated at capture/retrieval time, using offset-aware
timestamps, coherent camera/burst/vision metadata and matching latest images,
published producer status, hashes/archives, and existing environmental QC rules.
This deliberately remembers that evidence was admissible when published:
unconsumed evidence aging out must not erase an overdue reconciliation failure.
No current KNOWN value is copied into the snapshot by this check.

| Result | Meaning |
|---|---|
| CURRENT | Comparable admissible source content matches the snapshot evidence |
| PENDING_RECONCILIATION | Different source content; snapshot is within 30-minute grace |
| STALE | Different source content; snapshot exceeds 30-minute grace |
| SOURCE_UNAVAILABLE | Declared unavailable or no QC/freshness-eligible rows at retrieval; retain UNKNOWN |
| ERROR | Missing/invalid file, incoherent cycle, invalid digest/timestamp or missing provenance; cannot certify freshness |

Materiality is deterministic: camera cycle/health/vision/image identity; latest
eligible ASOS fields, river series (including method and qualifier identity),
and Weeks Bay parameters; or normalized NGOFS2 model guidance and coverage.
Fingerprints retain values, QC, units, location/depth and source identity. They
exclude retrieval bookkeeping. Same-time value/QC/coverage corrections are
detected even when timestamps do not advance. Unchanged re-retrievals and JSON
formatting alone do not require resynthesis. All model products remain MODEL;
regional proxies remain proxies. Blank/stale/rejected measurements are not zero.
Published NGOFS2 grid slices rely on the existing producer validation contract;
this guard checks the archive digest, normalized structure and model identity,
not a second physical model recalculation.

## Post-publication reconciliation and read-only status

The existing `Jubilee Current State Freshness` workflow now has one dedicated
writer job followed by the existing independent read-only status job. It runs
on relevant main pushes, sensing/ASOS/observation workflow completion (including
partial failures), manual dispatch and the existing half-hour schedule. The
completion hooks cover producer `GITHUB_TOKEN` pushes, which do not trigger
other push workflows. No acquisition schedule, camera coordinator, sensing
publication gate or additional scheduled workflow is introduced.

Only the writer job has `contents: write`. PRs run offline regressions only;
privileged `workflow_run` execution always checks out main and never downloads
producer artifacts or executes the triggering run's head. The read-only status
runs even when reconciliation fails, retaining visible source-drift reporting.
GitHub queue delays remain possible; this is not a real-time execution SLA.

`publish_current_state.py` fetches main and builds in an isolated detached
worktree. `reconcile_current_state.py` reads source bytes from that exact Git
commit, applies existing source validation (plus ASOS raw semantic reparse),
and reevaluates sensor admission at issue time. Failed/corrupt committed
products fail closed. Declared unavailable products remain
SOURCE_UNAVAILABLE/UNKNOWN; retained normalized files are not read. A failed
producer can still have independently validated committed products; only these
published products are eligible, never its artifacts or dirty worktree output.

The publisher commits **only** the snapshot and bound forecast together and
uses a normal fast-forward push. If camera, sensing, observation, research,
policy or reviewed state publication advances main, the candidate is discarded
and both files are rebuilt using the newer commit and its executable rules.
There is no stale-pair rebase, force push, or overwrite of another publisher.
Retries are bounded to four; exhaustion fails visibly. Even a deduplicated
no-op rechecks main before claiming current. The shared workflow concurrency
group serializes writer invocations, while optimistic retries protect against
the independent producers. Duplicate triggers do not write again unless
consumed source/contract bytes or issue-time admission statuses change.

The builder retains the exact existing dated outlooks, probability ranges,
confidence, zero production weights and four-trigger strict >20% alert contract.
It does not extend outlook dates or create a calibrated probability model.
New camera event indications, changed camera failures without an already-active
material input-quality alert, or simultaneous loss of previously available
weather and river context require explicit review. When a material input-quality
alert is already active, a changed camera failure set is recorded as operational
context and reconciliation continues while the existing alert gate and its
notification are preserved unchanged. Active direct-event evidence still fails
closed. Recovery
history remains operational context and is not added as a forecast alert
trigger. This path does not send alerts.

Reviewed desktop acceptance receipts now retain bounded operational history;
current PASS requires exact capture/source binding and the existing capture
freshness limit. See [receipt rules](DESKTOP_ACCEPTANCE_RECEIPTS.md). Their
hashes and admission states participate in provenance and deduplication.

Manual tide/public-camera context remains explicitly historical and not
reassessed. No new human observations, shoreline measurements, biological
negatives, training controls or new desktop/dawn acceptance are claimed. Camera
staleness produces UNKNOWN even when published metadata is coherent. Stale
model forecasts lose current-guidance admission; absent slices are never filled.

Before publication, candidate output must pass exact forecast binding and the
unchanged source freshness guard. Regression coverage includes both orders of
back-to-back sensing/camera publication, explicit outages, corrupt archives,
unpublished files, issue-time expiry, real Git non-fast-forward races,
concurrent reviewed state, retry exhaustion and the no-op race. Tests use the
September 28 10:23 CT production snapshot shape with deterministic source
fixtures; they do not assert that live production is fresh.

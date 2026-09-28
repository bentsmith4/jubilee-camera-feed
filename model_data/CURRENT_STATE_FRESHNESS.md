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

## Execution and scope

The independent `Jubilee Current State Freshness` workflow runs on relevant
main pushes, producer workflow completion (including mixed-success runs), manual
dispatch and every 30 minutes. Completion triggers cover GITHUB_TOKEN pushes
that cannot trigger downstream push workflows. Scheduled checks let a pending
status expire without another source update. GitHub scheduling can be delayed;
this is a policy check, not a guaranteed real-time SLA.

The live job always checks a pinned checkout of latest main, publishes a job
summary and JSON artifact, and fails visibly for stale/uncertifiable state. Its
permissions are read-only and its concurrency group is independent. It is not
called from, needed by, or used to gate any sensing publication job. PRs run
deterministic fixture regressions only; source drift must never become a failing
live assertion inside the producer's offline test suite.

Coverage: six owner camera metadata/image groups, ASOS, river forcing, Weeks
Bay and five separate NGOFS2 products. Public-player observations, manually
entered tide predictions, human reports, desktop burst archives and dawn
acceptance are outside this guard. Exact snapshot/forecast binding remains the
separate `Jubilee Forecast Consistency` check. A freshness PASS does not imply
that check passes, that sensors are fresh now, or that a Jubilee alert is due.

Remediation is explicit review/reconciliation of the differing source products,
followed by publishing the assessed snapshot and its bound forecast together.
Do not advance timestamps, rewrite provenance, or promote inputs merely to make
this check green. This PR intentionally leaves all production state unchanged.

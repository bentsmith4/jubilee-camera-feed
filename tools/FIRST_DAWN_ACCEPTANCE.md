# One-time September 29 dawn acceptance

Owner request: first complete dawn after the September 28 10:55–10:58 CDT
PointClearPC deployment in issue #26. Deployment source is
`d56f884596ab8709dfd78d57e5317784c2ea25d4`; reconciliation merge is
`4da28a059e29055390cac15602c368646764030e`.

## Event and lifecycle

`first_dawn_acceptance.yml` listens to canonical metadata pushes on main.
Only the **first** `Latest Jubilee camera burst - ...` commit with capture time
inside September 29's dawn window arms the observer. The deployed observer's
Astral 3.2 civil dawn is **06:19:45.673391 CDT**; its window is
**04:19:45.673391–08:19:45.673391 CDT**. The astronomical calculation is independently
checked in regression tests. No first canonical event means no observer starts;
this is intentionally not a scheduled substitute or an acquisition watchdog.

One bounded Actions job waits through the full window, then inspects immutable
Git history and actual downstream job logs. It begins final settlement checks
at 08:29:45 CDT and waits no later than 09:04:45 CDT for missing downstream
evidence. Missing/unavailable evidence at that deadline is **FAIL acceptance**,
with the evidence gap distinguished from a proved camera failure.

The observer posts one final PASS/FAIL comment in issue #26, mentioning the owner,
and retains a JSON artifact for 30 days. A durable comment marker plus a dedicated
non-cancelling concurrency group prevents duplicate reports on duplicate events
and reruns. Subsequent queued push jobs only check the gate and exit; GitHub may
cancel replaced pending jobs. There is no schedule, no repeated acceptance, and
no execution for other dates. The workflow's date gate remains inert afterward.
A platform outage that prevents the Actions job or final issue POST itself is
not something a repository workflow can guarantee notification through; Actions
failure status/artifacts remain the recovery path. A manual rerun deduplicates
against the final receipt, never silently replaces it.

## Acceptance contract

- Enumerate first-parent camera publication history, including the preceding
  baseline and first post-window capture. Require reviewed deployment and
  reconciliation ancestry, one parent per camera commit and publisher-allowlisted
  changes. Inspect committed bytes, never unpublished producer artifacts.
- Require the exact six owner cameras, successful capture/burst/vision, three
  numbered ordered shots, the existing 5–30-second shot integrity bounds,
  complete vision shot identity, latest-equals-third-shot metadata/bytes, and
  decodable latest JPEGs. Darkness remains biological UNKNOWN; this is an
  operational acceptance, not a visual non-event assertion.
- Enforce at least 900 seconds between capture starts, including both handoffs.
  Also enforce at least 900 seconds from preceding publication to next capture:
  publication precedes coordinator success, so this is a necessary lower bound
  on the deployed completion-based gate. It is not a claim to have read the
  private coordinator's actual completion timestamp or unpublished attempts.
- Check normal cadence by the deployed fixed 20-minute **slot** contract and
  report actual intervals and slot delays. The 15-minute completion floor may
  defer a slot's start. Require all twelve positive-duration slots; slot 12 exists
  only at the exact final microsecond in `capture_service.slot()` and is audited
  if present rather than inventing a thirteenth positive-duration slot.
  Any repeated-slot capture is adaptive and requires explicit fresh stronger
  activity in the preceding published vision, before civil dawn. Weak, stale,
  absent or post-dawn activity cannot justify it.
- For every dawn capture, require its immutable observation record with matching
  input hashes, six camera integrity passes and unchanged training/production
  guards, plus an actual successful unattended-logging job receipt for that record.
- For every dawn capture, require successful reconciliation and current-state
  status jobs with JSON receipts, the exact camera input hashes, a bound
  snapshot/forecast pair, committed source-provenance hashes and valid ancestry.
  Reconciliation must occur within the existing 30-minute limit. A green job
  whose guard says PENDING_RECONCILIATION is insufficient. Cancelled runs are
  reported separately and require matching successful replacement evidence.
  Explicit failed/timed-out dawn-triggered jobs, and observation/freshness jobs
  started during dawn through the final dawn capture's 30-minute settlement,
  remain acceptance failures, with failed step names in the evidence report.
- Finally run the existing full source-admissibility/freshness guard and forecast
  binding check on one pinned main tree. Explicit SOURCE_UNAVAILABLE/UNKNOWN is
  retained; corrupt evidence and stale/pending reconciliation do not pass.

The workflow token has contents/actions **read** and issues **write** for the
single receipt. It does not capture, restart, alter cadence, rerun producers,
repair/publish snapshots, change probabilities/weights/thresholds, or access
private desktop archives or R2. Signed log downloads never receive its token.

Regression: `python -B -m unittest discover -s tests -p 'test_first_dawn_acceptance.py' -v`.

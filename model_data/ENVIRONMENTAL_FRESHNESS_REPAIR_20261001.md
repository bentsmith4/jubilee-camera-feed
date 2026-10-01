# Environmental freshness investigation — October 1, 2026

Evidence inspected at main `9ce99555c0b382e58fe8023e4f904a3db07e8092`.
This is an engineering diagnostic, not a Jubilee prediction or fault clearance.

## Verified source state

The earlier claim that source commits stopped in September is superseded by
[source snapshot 6a18291a](https://github.com/bentsmith4/jubilee-camera-feed/commit/6a18291a26dce968d45c7e5fcbacf1aa8a895335),
committed October 1 at 10:43:32 UTC. Path-specific commit history also shows
October 1 snapshots at 05:35 and 01:07 UTC.

| Source | Verified receipt | Attribution |
| --- | --- | --- |
| USGS lower river | Retrieval 10:26:51 UTC; 29,506 rows, all three sites and 20 method-specific series. Latest observations 09:30–10:00 UTC; 26.86–56.86 minutes old at retrieval. | Successful provider response and repository publication. Later expiry is distinct from request failure or QC rejection. |
| WKQA1 | Retrieval 10:26:52 UTC; latest parsed observation September 9, 16:15 UTC; unchanged raw hash. | Provider-served observation gap in this NDBC product. Transport and parsing succeeded; no claim about the underlying instrument cause. |
| WKXA1 | Same retrieval; latest observation 09:45 UTC. | Fresh at retrieval; repository cadence can subsequently make it stale. |
| NGOFS2 named forecast | Whole process exceeded 480 seconds at 10:43:01 UTC. | Unresolved provider/client cause. A process deadline does not establish a NOAA outage. |
| Other NGOFS2 products | Point Clear nowcast/forecast, named nowcast and shoreline grid completed in this run; some newer files returned NetCDF file-not-found and older cycles were selected. | Partial product availability; neither an all-provider outage nor a guarantee of issue-time freshness. |

[Sensing run 36849032885](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36849032885)
was a scheduled run, started 10:25:25 UTC, and published successfully. The logged
named-forecast deadline was preserved even though continue-on-error made that
step's *conclusion* appear successful. Product manifests remain authoritative.

## Ingestion, retry and publication paths

- River: bounded 25 MB response; three requests with 60-second socket timeout
  and 1/2-second backoff. Qualifiers, estimated flags and gate-method identity
  remain explicit. Freshness is recomputed at synthesis time, not taken from
  the manifest's retrieval-time `fresh` boolean. Network/HTTP outages become
  unavailable; repeated outages escalate. Schema defects remain failed.
- Weeks Bay: each station is fetched independently, up to three 45-second
  attempts and 1/2-second backoff, capped at 5 MB. Successful parsing is not
  equivalent to fresh observations. Partial station results are retained;
  complete failure stops subsequent ordinary workflow steps. Failed producer
  outputs are excluded from the publication allowlist and retained as artifacts.
- NGOFS2: recent-cycle fallback precedes extraction. Four station-product
  processes each have a 480-second budget; shoreline grid has 720 seconds.
  NetCDF operations can block inside the library. The wrapper kills the timed
  out process and writes a receipt. Validation removes current CSVs for an
  accepted retrieval failure, preserving immutable archives. Parser/schema
  failures remain fatal and do not gain publication permission.
- Publication: offline regressions gate writes; producer *outcomes* gate
  allowlisted files. A clean worktree rebases and retries publication three
  times. Concurrent source-registry metadata is preserved and ingestion fields
  are regenerated. This run's rebase and push succeeded.

## Repository cadence and reconciliation failures

`sensing_quality.yml` requests `37 */3 * * *`; river observations expire after
180 minutes, WKXA1 weather after 90 minutes. Three-hour acquisition leaves no
river freshness margin and cannot continuously satisfy WKXA1's shorter limit.
Sequential NGOFS2 work delays publication of already retrieved observations;
the maximum configured NGOFS2 budgets total 44 minutes, within a 50-minute job
that must also test, ingest other sources and publish. GitHub schedule execution
is not demonstrated to match its requested minute: this scheduled run started
at 10:25. ASOS has a separate hourly workflow but shares sensing concurrency.
No cadence or budget is changed by this diagnostic patch.

[Freshness run 36884408320](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36884408320)
failed reconciliation at 15:28 UTC with
`REVIEW_REQUIRED: retain active assessed event/fault until explicit review`.
Offline regressions passed. The committed snapshot remains 08:27:51 CDT with
`material_critical_input_fault=true`; the later ASOS receipt alone does not clear
that assessed fault. The guard deliberately blocks automatic fault replacement.
It must not be described as a provider failure or silently bypassed.

## Focused correction and verification

Timeout receipts now record product, start time, configured budget and explicitly
unresolved provider/client attribution. The availability reason becomes
`retrieval_timeout_cause_unresolved`, including for legacy timeout receipts.
Confirmed DAP server errors retain their existing attribution. Availability,
CSV removal, parser rejection, probability values, zero production weights,
strict `>20%` threshold and the user's 9 PM Central reporting policy are unchanged.

Offline verification: 8 NGOFS2 availability tests, 19 publication tests and
15 current-state reconciliation tests pass. Tests cover every product budget,
legacy receipts, unaffected products, immutable archives, stale CSV removal,
parser rejection, UNKNOWN semantics and unchanged forecast bindings.
The additional freshness suite passed 23 checks; its production NDBC archive
replay could not run in the connector-reconstructed checkout because binary
gzip fetches are unsupported. This is a local verification limitation, not a
parser assertion failure; the complete repository CI must run that replay.

Remaining work is separate from this diagnostic: obtain phase-specific NGOFS2
timing before changing timeouts; decouple fast-source refresh/publication from
slow model retrieval if continuous freshness is required; explicitly reassess
the active fault using issue-time evidence. WKQA1 cannot be restored by faster
fetches of the same unchanged provider product.

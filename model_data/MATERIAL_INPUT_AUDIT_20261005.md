# Material-input fault audit — October 5, 2026

## Verified result

The publication freeze is resolved. The source-age loss was operational, not evidence of missing scientific sensors: configured GitHub cron triggers did not produce the promised cadence. Successful acquisitions resumed without parser changes. The material fault remains explicitly latched by the current-state reconciler; it is not recomputed from the count of current UNKNOWN fields and is not cleared by this change.

Audit evidence baseline: main `a5b56ba` (camera publication), including canonical pair from `8616342` at **11:09:28 AM CT**. This is newer than the 10:14 AM state that motivated the audit. ASOS at 10:47:20 AM CT admits wind speed/direction, air temperature, dew point and pressure for both KBFM and KMOB; blank/missing gust and precipitation fields remain UNKNOWN and KBFM three-hour precipitation remains TRACE. River retrieval at 10:23:05 AM CT yields **20/20 fresh qualified upstream-proxy series** at that issue time. All six camera metadata views pass; this does not establish independent archive acceptance or biological absence.

## Separate fault classes

| Class | Finding | Evidence that would clear or improve it |
|---|---|---|
| Operational scheduling | ASOS promises hourly acquisition but last scheduled runs were 1:44:54 AM and 10:46:42 AM CT; the former completed 1:45:51 AM. Sensing promises three-hour acquisition but scheduled runs began 1:09:18 AM and 10:12:49 AM CT. Successful ingestion does not prevent nine-hour source gaps. | Repeated camera-triggered or scheduled refreshes producing qualified observations within unchanged age limits; verify the new event path on main and subsequent cycles. A single successful refresh does not prove future scheduler reliability. |
| Actual source acquisition | Overnight named-stations forecast exceeded the 480-second whole-process budget. The next two sensing runs published unavailable model slices; the latest named nowcast/forecast and Point Clear forecast show `NetCDF: DAP server error`. | Successful retrieval with accepted station/cell/vertical mapping, archive hashes and readback, valid-time coverage and issue-time admission. Preserve old timeout attribution as unresolved; a later DAP error does not retrospectively establish the cause of that timeout. |
| Scientific/design limitations | Direct local bottom/contact-strip DO, salinity/temperature profiles and stratification; local observed currents/water level and shoreline meteorology; calibrated river-to-Bay travel time; out-of-view biological outcomes remain UNKNOWN. Airport, upstream river, Weeks Bay and modeled NGOFS2 values do not replace those observations. | Validated direct measurements at the relevant cell/depth/time, qualified observations and held-out calibration evidence appropriate to each claim. One Montrose instrument cannot establish Point Clear currents. |
| Assessment lifecycle | `material_critical_input_fault=true` and `notification_condition_met=true` are preserved assessed gates. Reconciler explicitly copies the prior fault and emits `assessed_material_critical_input_fault_preserved=true`; new/recovery notification flags are false. | An explicit scoped recovery assessment against the original fault and current accepted evidence, followed by a correctly bound state/forecast pair. Fresh ASOS/river alone do not authorize automatic clearing, especially while model slices remain unavailable. |

## Source-age and schedule audit

- ASOS freshness is **90 minutes from observed time**, not retrieval time. Future/unavailable observations, blank rain and QC-rejected values remain UNKNOWN; zero and TRACE have distinct meanings.
- River series freshness is **180 minutes from latest observed time**, with per-series qualifiers and method IDs retained. This is independent of the upstream-to-Bay lag, which is uncalibrated. A nominal three-hour ingest interval has no allowance for observation latency, runtime or publication delay, so it cannot ensure continuous fresh admission even when cron works.
- Weeks Bay water proxy freshness is 180 minutes; station meteorology uses 90 minutes. These are regional context and not Eastern Shore bottom observations.
- Camera metadata freshness is 60 minutes. Archive acceptance and biological detectability are separate checks.
- NGOFS2 nowcast, forecast and shoreline products have separate valid-time and availability checks; a newer unavailable manifest does not authorize reading a retained older CSV. The existing budgets remain 480 seconds per station product and 720 seconds for shoreline-grid retrieval. The availability validator treats recognized DAP errors as source unavailable but refuses unclassified/parser defects. Workflow success consequently means QC/publication completed, not that every source is available.
- `.github/workflows/asos_weather.yml`: `7 * * * *`; `.github/workflows/sensing_quality.yml`: `37 */3 * * *`. Both retain shared sensing concurrency. Run creation gaps demonstrate trigger-delivery failure/delay, rather than nine-hour execution time. No claim is made that the exact GitHub infrastructure cause is known.

## Small operational correction

Extend the existing lightweight ASOS job, rather than adding a separate polling service:

1. Trigger on main `status.json` camera publications as well as the unchanged hourly cron, dispatch and existing code paths. Actual camera pushes already trigger observation logging and freshness reconciliation; this supplies an event fallback independent of cron. It neither captures cameras nor changes camera cadence.
2. Refresh qualified USGS lower-river data in that same lightweight job using the existing 16-day ingest and publication allowlist. Shared concurrency serializes it with full sensing; producer outcomes preserve independent ASOS/river success and prevent failed producers from staging their files.
3. Retain append-only public archives, artifact evidence, clean-worktree rebase/publication and persistent-river-outage escalation. Ingest commits modify neither `status.json` nor the trigger code paths, so they do not create a reply-style workflow loop.

The fix mitigates the demonstrated scheduler gap; it cannot guarantee freshness if both GitHub scheduling and camera publication stop, if shared sensing holds the job too long, or if the sources stop publishing. These conditions continue to be UNKNOWN/fault evidence. It does not assert that a nine-hour trigger gap is scientifically expected.

No NGOFS2 parser/extractor change is justified by the observed errors. The named-station extractor performs scalar remote reads and could be optimized, but the available logs do not isolate those reads as the cause of the overnight timeout. Increasing its budget or labeling the old timeout as a confirmed provider outage would not resolve that evidence gap.

## Reproducible run evidence

- [Overnight sensing run 37270986336](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37270986336): river started 1:10:54 AM CT; forecast whole-process timeout logged 1:24:02 AM CT.
- [Overnight ASOS run 37273984953](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37273984953): success; completed 1:45:51 AM CT.
- [Latest sensing run 37330975327](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37330975327): success; fresh river/ASOS independently published, failed NGOFS2 slices explicitly unavailable.
- [Latest ASOS run 37335555978](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37335555978): scheduled, success; completed 10:47:28 AM CT.

## Preserved boundaries and validation

The patch does not edit the state/forecast pair, sensor freshness limits, NGOFS2 budgets, probability ranges, strict >20% comparator, production weights, notification policy or 9 PM feedback gate. Existing source normalization, issue-time QC and UNKNOWN handling are unchanged.

Local checks: 26 ASOS tests, 5 USGS method/QC tests and 19 producer-gated publication tests pass (50 targeted tests). Workflow YAML parses and every shell block passes `bash -n`. Full regression/remote CI and deployed-run readback are recorded in the pull request; they must not be implied by this static audit.

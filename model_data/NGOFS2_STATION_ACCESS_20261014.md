# J04 NGOFS2 station access investigation — October 14, 2026

**Disposition: station HTTP correction implemented and isolated-live-tested; GitHub review and ordinary scheduled-cycle acceptance pending. No deployment or predictive-skill claim.** Research owns J04 dataset acceptance and J09 geometry; Sensing owns collection; the existing Jubilee Dot coordinates. PR #83's normalized-field mapping and historical DAP-error handling are preserved.

## What failed, and what is established

Baseline: main `f8b874a128684414639a9b8ae430e92e2fafbe0e`. Its October 14 16:11 CDT snapshot follows station collection at 17:35–17:39 UTC: all four Point Clear/named-station products are unavailable with `RuntimeError: NetCDF: DAP server error`. The 17:39 UTC grid manifest is complete with 1,848 rows, but it fell back from the absent 15Z grid to 09Z.

Both station collectors previously opened the same `.../thredds/dodsC/NOAA/NGOFS2/MODELS/YYYY/MM/DD/ngofs2.tCCz.YYYYMMDD.stations.{cast}.nc`. They then made repeated lazy remote reads, including per-time/per-layer scalar reads. Their cycle fallback covered opening the dataset, **not** later extraction failures. The grid collector reads separate regular-grid files and batches numerical fields into bounding rectangles. Its success is therefore neither station-path recovery nor station equivalence.

The precise historical failing variable and NOAA server/client internal cause remain unresolved. The saved error lacks that traceback. Bounded, URL-encoded ASCII and binary DAP requests for station names, coordinates, time and currents succeeded in this investigation. A local libnetcdf open probe returned `-68 I/O failure`, distinct from the retained `-70 DAP server error`; that local result is not proof of NOAA failure. Do not describe the entire NOAA service as down or recovered.

**The original station files are available by HTTPS.** The October 14 09Z nowcast from THREDDS `fileServer` and NOAA's S3 mirror was byte-identical: 14,831,795 bytes, SHA-256 `0d5a2a17945c4b746d2e2e0d4f6ea1d1100fd8003c10a4dba55d0441b8bb0cee`. The newer 15Z station nowcast and forecast also downloaded and decoded successfully. Thus changing access method is supported without substituting a different scientific product.

## Small correction

- Both collectors use a shared bounded HTTPS downloader: official NOAA S3 station object first, same-cycle THREDDS fileServer second, then the existing ordered cycle candidates only for explicit retrieval failures. Existing 90-minute posting cushion, eight-cycle search and whole-process budgets are unchanged.
- Open the complete downloaded NetCDF locally, eliminating lazy DAP extraction calls. Enforce a 160 MiB size limit, 20-second socket timeout and 90-second streaming budget; the existing process watchdog remains the outer bound. Validated forecast file size is 116,012,123 bytes.
- Check NetCDF signature/length, NGOFS2 title and **embedded** complete six-minute valid-time coverage against the requested cycle/cast. Wrong cycle, wrong cast, partial series, invalid data and parser errors fail closed without trying an older dataset. Retry only selected HTTP availability statuses and URL/time-out failures. Authorization/bad-request errors remain fatal.
- Retain full-file SHA-256, bytes, actual source URL, completion time and validation receipt in the manifest and archived extracted subset. `available_at` is assigned after the download/validation completes, not when collection starts. Existing normalized columns, station mapping, sigma-layer selection, shoreward projection and archived subset behavior are unchanged.
- Preserve structured failures. Exhausted HTTP retrieval remains unavailable, old affected CSVs are removed by the existing availability validator, and the reason explicitly leaves provider-versus-client attribution unresolved. PR #83's DAP-specific historical classifier remains intact.
- One workflow path entry recognizes the new helper as a dependency; no schedule, job, timeout, camera or alert change.

## Geographic, vertical, directional and temporal acceptance

| Requirement | Station file result | Grid limitation / disposition |
|---|---|---|
| Geography | Official model station `8733821 Pt Clear, MB`, index 93, 30.48903275 / -87.93621826, about 0.311 km from the public Point Clear target. Both extractors select the same station. | Four Point Clear cells are about 0.644, 0.906, 1.529 and 3.419 km from the anchor. Requested offshore offsets are not actual cell distances. Interpolated 0.01-degree grid cells are not the named station or shoreline contact strip. |
| Bottom depth | Model bathymetry 1.83 m; 40 sigma layers; surface sigma -0.0125 and bottom sigma -0.9875. Bottom center lies 1.25% of the instantaneous modeled water-column thickness above the bed, not on the bed. | Deepest finite standard depths are 1, 1, 2 and 2 m in bathymetry 1.993, 1.964, 2.999 and 3.969 m. Nominal `h-depth` gaps are 0.993, 0.964, 0.999 and 1.969 m. Precise instantaneous clearance additionally requires the depth datum/free-surface interpretation. These cannot replace the station bottom sigma layer. |
| Direction | Actual `u`/`v` attributes identify eastward/northward sea-water velocity, meters/s. Existing provisional 090-degree shoreward projection remains positive eastward. Numerical projection regression tests pass. | Grid uses eastward/northward components and the same provisional shore normal. This establishes a mathematical projection, not validated local shoreline geometry or observed onshore transport. |
| Validity | 15Z nowcast: October 14 09:00–15:00 UTC, 61 times. Forecast: October 14 15:00 through October 16 15:00 UTC, 481 times. Embedded times validated, nowcast/forecast kept separate. | 09Z grid nowcast has only 06:00/09:00 UTC; forecast has 09:00/12:00/15:00/18:00/21:00 UTC. Three-hour spacing cannot recover six-minute transport variability. Existing requests for n/f001, 002, 004, 005 fail because these are not published 3-D regular-grid hours. This ancillary inefficiency is documented, not changed here. |
| Freshness and availability | Existing 180-minute nowcast transport gate and as-of availability check remain unchanged. Isolated retrieved 15Z nowcast was ~397 minutes old at assessment and correctly returned `UNKNOWN_STALE_MODEL_TRANSPORT`, value null. Forecast coverage is evaluated at its own valid times, never relabeled as observed/antecedent current. | Grid newest nowcast was already ~519 minutes old at its 17:39 retrieval. “Complete” is collection status, not fresh guidance. Grid forecast future timestamps do not make the old nowcast current. |

Named-station caveat retained: Fly Creek resolves to Blakeley Pass Entrance about 8.9585 km away, with its existing proxy warning. It is not an in-cell Fly Creek observation. Meaher and other named-station geometry stays as recorded; this change does not repair or promote those geographic proxies.

**Grid substitution is rejected for this correction.** Any future grid-bottom alternative needs validated native FVCOM node/element mapping, wet/dry status, bathymetry and sigma/free-surface depth conversion, vector frame and local shore normal, explicit time resolution/coverage, issue-time freshness/availability, and same-cycle station/grid comparison. Native 3-D fields can supply those inputs; surface-only `2ds` cannot establish bottom conditions. Neither station nor grid supplies direct dissolved-oxygen observations or proves Jubilee skill.

## Validation evidence

Machine-readable receipt: [ngofs2_station_http_acceptance_20261014.json](ngofs2_station_http_acceptance_20261014.json). All collection outputs were generated in an isolated scratch directory, not over live repository products.

| Product | Rows | Unique valid times | Full collector elapsed |
|---|---:|---:|---:|
| Point Clear nowcast | 671 | 61 | 5.710 s |
| Point Clear forecast | 5,291 | 481 | 8.051 s |
| Named-station nowcast | 2,745 | 61 | 5.208 s |
| Named-station forecast | 21,645 | 481 | 10.048 s |

These are 30,352 parameter rows, not independent observations/events. Every isolated normalized row exactly matched the baseline extractor run on the same full station file with the same source URL and availability timestamp. All rows retain MODEL classification and weight zero. Exact full-file, normalized-CSV and archived-subset hashes are in the receipt.

Local tests: 40 NGOFS2 transport/resolution/access/availability regressions and 18 Meaher loading/transport regressions pass. Cases cover wrong cycle/cast, missing time coverage, payload truncation/HTML/oversize, bounded download time, same-cycle failover, structured network failures, parser/auth failures, stale-row removal, UNKNOWN/null preservation, existing freshness boundaries and future-availability exclusion. Tests validate implementation safety, not ocean-model or Jubilee forecast accuracy. Exact-head GitHub checks are tracked in the PR.

## Review and Dot handoff

Keep this under existing **J04 / Research**, with **Sensing** scheduled collection acceptance and **J09** scientific geometry gates. Current AGENTS, charter, register, open PRs and portfolio ledger version 35 were checked. No competing station-access correction was found. Do not repeat PR #83 or create another collection scheduler/research ledger.

Native Dot access in this session exposed a signed-out 404 at its recorded UI route; **new native acknowledgment is pending**. The existing prior Research & Calibration handoff remains valid. At the next authorized review, consume this PR and its exact evidence; independently acknowledge the version. After separate merge approval, verify one ordinary scheduled main collection, all four manifests/CSV/archive hashes and downstream UNKNOWN/freshness behavior before claiming service restoration. No forced production run or PointClearPC action was performed.

Production weights, forecast probabilities, UNKNOWN handling, sensing schedules, alert thresholds and the 9 p.m. America/Chicago notification restriction are unchanged. No predictive promotion, merge, deployment, paid call or outreach is included.

## Primary access documentation

- [NOAA OFS FAQ](https://tidesandcurrents.noaa.gov/ofs/ofs_faq.html): official S3/THREDDS/NOMADS access; station six-minute versus NGOFS2 3-D three-hour output; 48-hour forecast; 2025 S3 directory layout; regular-grid interpolation.
- [NOAA Mobile Bay NGOFS2](https://tidesandcurrents.noaa.gov/ofs/ngofs2/ngofs_mobile.html): model scope and official archive links.
- [Completed PR #83](https://github.com/bentsmith4/jubilee-camera-feed/pull/83): mapping and unavailable reporting, not NOAA recovery.

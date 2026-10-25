# October 22 NGOFS2 forecast rejection: forensic follow-up

Existing ownership: J01 Sensing & Alerting / J04 source reliability; Research reviews model-data evidence; Jubilee Dot consumes this receipt through MODEL_WORK_REGISTER.md. Inspected main: fe3f47d. This investigation does not reopen the incident cleared by PR #133.

## Finding and limits

The presently retrievable October 22 03Z forecast contains three embedded timestamps one second earlier than the exact six-minute grid. Both official NOAA copies are byte-identical and reproduce the original error under the unchanged validator. This establishes a source-file clock inconsistency in the recovered product, not a permissive-parser defect. It strongly supports that explanation of the historical failure, but does not establish identity with the bytes downloaded during the original failed jobs: those jobs retained neither the rejected NetCDF nor its hash. No claim about how NOAA generated those three values is supported.

The October 24 09Z replacement was independently downloaded again. Its full-file hash exactly matches PR #133's accepted product, and its 481 timestamps pass the unchanged validator. No acceptance tolerance, rounding or automatic fallback is justified by this evidence.

## Prior-work and evidence recovery

PR #133, its dated recovery assessment, the current work register, GitHub NGOFS2 issue/PR searches and retrieved prior-work context contained recovery evidence but no completed underlying clock investigation. No competing investigation PR was found. The original run is [39734344678](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/39734344678); jobs 119676441726 and 119678512221 both retain the generic embedded-valid-times error for both forecast collectors. Successful nowcasts in those runs are separate products.

Both original artifacts were downloaded and SHA-256 verified against GitHub's artifact digests:

| Attempt | Artifact ID | ZIP SHA-256 | Contents |
|---|---|---|---|
| 1 | 12406880303 | 662466577854ac10ddb43d6bdc297a60fa290ea3a13366f40810c5e7ecc27fd6 | 3,152 entries; no NetCDF |
| 2 | 12406373448 | 0bfe3789c0c220754ac510ba6a1c944327931cedc786e40f0e5ce77d24abf190 | 3,154 entries; no NetCDF |

All four failed forecast manifests contain the generic ValueError, without a rejected-file hash, actual clock, selected source URL or selected-cycle receipt. Neither retained normalized CSV nor older accepted archive can substitute for those missing rejected bytes. The HTTP adapter creates its hash receipt only after validation, explaining the reproducible evidence-retention gap.

Fresh retrievals used the exact October 22 03Z forecast path on NOAA S3 and THREDDS fileServer. They each returned 116,012,123 bytes with SHA-256 `c3385108c34fbf0bd838ffe2e4f0d5499e9be9c4e95b0fef1b58c750d18c7e42`. Retrieval times, URLs, attributes, manifest excerpts and comparisons are recorded in `ngofs2_rejection_investigation_20261024.json`. These fresh retrievals are not retroactively labeled original-run evidence.

## Clock comparison

| Property | Recovered October 22 03Z | Accepted October 24 09Z replacement |
|---|---|---|
| Requested initialization UTC | October 22 03:00 | October 24 09:00 |
| Embedded first / last UTC | October 22 03:00 / October 24 03:00 | October 24 09:00 / October 26 09:00 |
| Timestamp count | 481 | 481 |
| Raw clock type / units | float64 seconds since 2019-01-01 00:00:00 | Same |
| Exact six-minute grid | 3 mismatches; all others match | All 481 match |
| Validator result | Rejected | PASS |
| Full-file SHA-256 | c3385108c34fbf0bd838ffe2e4f0d5499e9be9c4e95b0fef1b58c750d18c7e42 | a4ea05fd3d23e72b6c61e21d7d95e5a1d754607e195e2443cd1a5862984f00d2 |

The October 22 file identifies NGOFS2, with history `model started at: 22/10/2026   03:21`; that run-start string is distinct from requested model initialization and valid-time coverage. Only one embedded clock variable (`time`) exists. The three deviations exist in the numeric source values, not merely formatted timestamp display:

| Zero-based index | Actual UTC | Expected UTC | Offset |
|---|---|---|---|
| 323 | October 23 11:17:59 | October 23 11:18:00 | −1 second |
| 328 | October 23 11:47:59 | October 23 11:48:00 | −1 second |
| 333 | October 23 12:17:59 | October 23 12:18:00 | −1 second |

This yields 359/361-second adjacent intervals at each anomaly. The 48-hour endpoints and total count are correct; an endpoint/count-only check would miss the defect. The replacement retains PR #133's 11 Point Clear series (5,291 rows) and 45 named-station series (21,645 rows); these are two extracts of one file. This follow-up replays its source clock, not a new production ingestion.

## Narrow correction and test adequacy

The existing 49 NGOFS2 tests passed before changes. They cover normal nowcast/forecast clocks, wrong cast/cycle, partial coverage, corruption, HTTP failures and fatal-versus-unavailable behavior. They lacked a real interior one-second clock anomaly and verification that its diagnostic evidence survives both collector failure paths.

The proposed correction preserves the exact comparison and fatal behavior. A ValueError subclass carries bounded mismatch evidence; the adapter adds URL, requested cycle, byte count, SHA-256 and retrieval attempts before closing the dataset. Both collectors persist that diagnostic in their existing failed manifests, already included in run artifacts. No new workflow, storage service or raw 116 MB file is added. Diagnostics retain at most ten mismatches with the total count and truncation indicator; they are not a complete rejected-file archive.

The source-derived fixture contains both complete numeric clock arrays and full-source hashes. Four additional tests replay the recovered failure, accept the exact replacement clock, verify both collectors preserve evidence while availability validation still fails closed, and bound diagnostic output. All 53 NGOFS2 tests pass. Historical identity remains unverified even after this forward-looking correction.

No production snapshot, forecast probability, weight, schedule, alert threshold, UNKNOWN behavior, fault latch or 21:00 America/Chicago notification restriction changes. No alert or outreach was sent. Publication/review/merge and ordinary-cycle acceptance are separate from the local test result.

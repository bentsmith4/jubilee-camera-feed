# Camera failures during severe weather — October 7, 2026

Scope: offline inspection and regression coverage at main commit
`c834346319766292fceaf3d77a2fe43d24daf4f7`. The production runtime remains
`C:\JubileeCams`; this repository is its mirror. No production code, current
state, probabilities, weights, alert gates, freshness limits or schedules changed.
No additional capture owner or scheduled task was created.

## Observed state

The inspected `status.json` capture is October 7 at 15:06:32.525359 CDT.
All six cameras have `ok=true` and `burst_count=3`. This audit does not establish
a live outage or independently inspect those pixels. The supplied NHC advisory
URL could not be retrieved; storm identity, track and watches were not independently
verified and are not inputs to these offline tests.

## Failure behavior

| Failure boundary | Existing behavior | Negative-evidence protection / limit |
|---|---|---|
| Individual canonical stream | Two bounded attempts; failed camera gets `ok=false`; loop continues to other cameras | Failed camera has no successful burst shots. GitHub payload omits/deletes its latest JPEG even if old local pixels remain. |
| Entire site or all six streams fail after setup | Per-camera handling continues and writes failure metadata for all expected devices | Capture success/exit code means the capture step completed, not that cameras were healthy. Complete-outage publication still depends on later analysis/upload stages succeeding. |
| Device missing from inventory | Expected ID is explicitly inserted as failed | No healthy placeholder or inferred quiet frame. |
| Failed burst or missing burst image | Analyzer skips that camera and continues analyzing healthy cameras | Skipped rows have `burst_not_ok`/`burst_image_missing`, with no quiet biological classification. An incomplete set cannot use the deterministic all-camera quiet shortcut. |
| Poor visibility / low detectability | May retain raw upstream quiet/unclear labels as qualified context | Observation-effort gate rejects a shoreline candidate; shared-state rows forbid negative event labels. A raw `none` is not a verified non-event. |
| Stale, incomplete, mismatched or missing evidence | Observation-effort integrity rejects control eligibility; shared-state admission expires old data or rejects inconsistent metadata | Clean-training-negative count remains zero. Malformed JSON/incoherent metadata can fail the job rather than publish a new UNKNOWN record; prior output is dated, not refreshed. |
| Newly changed failure set | Automatic state reconciliation requires material-fault review if no material fault was previously assessed | Fails closed without writing a new state/forecast pair. This is deliberate review gating, not an automatic new alert inference. |
| Failure under an already assessed active material fault | Reconciliation can refresh source context while preserving the assessed fault/alert gates | Failed feeds explicitly `UNKNOWN_STALE_OR_FAILED`; healthy feeds remain admitted; outlooks and zero-weight governance unchanged. |
| Authentication, inventory or browser startup failure | Can stop capture before fresh failure metadata is written | Last publication remains dated; not every outage immediately creates new UNKNOWN metadata. Existing issue-time freshness checks must be consumed. |
| Vision API, archive/upload or mirror failure | Can stop the canonical pipeline; analysis API failure is not isolated per camera | Healthy capture does not guarantee publication. Old products cannot be called a fresh successful cycle; exact recovery/notification delivery remains a runtime acceptance task. |

The GitHub publisher refuses stale cycles, future timestamps, mismatched product
identities, invalid successful-camera JPEGs and private data. It preserves Git
ancestry and does not overwrite live model commits. R2 upload skips failed
camera media and publishes status last; a bare old image URL is not current
evidence without matching health/timestamp metadata.

Montrose's qualifying primary view is `montrose_shoreline`. Healthy ancillary
views cannot rescue an unavailable primary. If that primary remains usable while
other views fail, the existing policy permits only a visible-scope candidate;
it still does not create a clean training negative. Point Clear marina/Bay views
do not establish a clean beach/swash-zone control even when healthy.

## Added regression coverage

- All 64 healthy/failed combinations across the six cameras, deliberately
  retaining old quiet images/vision after capture failure.
- Site-wide Montrose and complete six-camera failures through real capture-loop
  logic and GitHub payload generation, using mocked acquisition and no network.
- Missing products/camera/image, corrupted image, incomplete burst, mismatched
  identity, stale capture, poor visibility, low detectability and unknown signal.
- Analyzer routing for failed feeds, missing images and complete outage. Camera
  and synthesis API results are mocked; this validates control flow, not model
  accuracy or what an actual empty-input synthesis request will return.
- New partial/complete fault review gate preserves the existing published pair.
- Already assessed partial/complete outages preserve frozen outlooks, weights,
  alert gates and state/forecast binding while keeping failed feeds UNKNOWN.

Existing tests additionally cover bounded retries/stream cleanup, diagnostic
redaction, archive integrity, same-device serialization and lock release on
error, coordinator backoff/recovery, freshness and publication race safety.

## Validation

`python -B -m unittest discover -s tests -p 'test_*.py'`: 448 tests,
zero failures/errors, five skips (PowerShell entry-point tests unavailable on
this Linux host). The full clone at the exact main commit was used for this
result; an earlier partial text export lacked historical fixtures and is not
the validation basis. Focused new outage test module: four tests passed,
including 64 outage combinations. Desktop/test compilation and `git diff
--check` passed. All API/acquisition outage simulations were offline.

## Windows acceptance still required

1. Read installed file hashes and actual running processes/task definitions at
   `C:\JubileeCams`; confirm one coordinator/capture owner and disabled predecessors.
   Mirror code and prior dated receipts cannot establish the present installation.
2. Verify controlled one-feed, site-wide and full-feed failures through real
   acquisition, vision, R2 and GitHub publication, then reopen/read back matching
   status/burst/vision identities and retained archive checksums. Do not induce
   failures in production without a safe isolated fixture/staging procedure.
3. Confirm Windows timeout `taskkill /T /F`, device-lock release, bounded retry,
   continuation of healthy streams and recovery on the next existing cycle.
4. Exercise real credential/browser/API/network failure recovery, process/service
   restart after a power interruption, and freshness/material-fault notification
   delivery. These are distinct from per-camera stream failure handling.

Actual Windows acceptance was not performed. No local runtime deployment or
storm-readiness guarantee is claimed.

## Repository integration verification — October 10, 2026

Reconciled this existing PR against main
`be30042235298261fe2b8e49b35426a870db162d`, including the already merged
compact-JSON analyzer. The register conflict was resolved by retaining every
byte of the current main register and appending this audit's historical entry
and the integration receipt. Relative to that main, only this audit, the
existing register and the three outage-test files change; runtime, workflows
and current camera/state products are unchanged.

The full offline suite ran 510 tests with zero failures/errors and five
PowerShell skips on the cloud Linux host. The 32 focused outage/capture/state
tests and 13 preserved J09 portable tests passed. Desktop/test compilation,
PR-delta whitespace validation and the committed desktop-receipt provenance
audit passed. An initial run lacked astral/netCDF4; the reported full pass is
the rerun after installing the repository's pinned test dependencies.
Independent read-only review found no blocking repository-integration defect.
Exact-head remote CI and merge status are tracked by existing PR #74.

This is repository-only verification within J01/J06/J13 under the existing
Sensing ownership. It does not validate the actual Windows installation or
end-to-end failure/recovery acceptance listed above. No live failure injection,
new acquisition, paid model call, deployment or scientific promotion occurred.

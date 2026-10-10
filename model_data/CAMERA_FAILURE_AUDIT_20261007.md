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

## PointClearPC bounded acceptance — October 10, 2026, 13:35–13:41 CDT

Status: **PARTIAL_WINDOWS_ACCEPTANCE; end-to-end acceptance remains open**.
This supersedes the historical statement that no Windows checks were performed.
Existing identity/owner: J01/J06/J13, Sensing, merged PR #74. No new coordinator,
automation, investigation or regression-development branch was created.

### Installation, ownership and recovery configuration

Remote Desktop Commander executed on PointClearPC. The staging checkout was
main commit `3dba1542aee65c18c26f1522286d2bff35f76774`; production remained
`C:\JubileeCams`, and its mirror working tree was not reset or pulled.
`Jubilee Live Cameras` is Running and invokes installed `live_loop.py`,
which delegates to `capture_service.main`. Its boot trigger is enabled,
multiple instances are IgnoreNew, execution limit is PT0S, StartWhenAvailable
is true, and restart is configured for three attempts at PT1M. These are
configuration facts, not a demonstrated reboot/restart receipt.
`Jubilee Dawn Cameras` and `Jubilee Unattended Test` are Disabled.
TCP coordinator lock 127.0.0.1:47651 belongs to PID 19016. The heartbeat
advanced during inspection. Task/lock evidence supports the existing single
scheduled acquisition owner; Win32_Process returned null command lines for
the other Python processes, so exhaustive process attribution is NOT_VERIFIED.

Installed SHA256:
- capture_service.py: `2598aa3eb1e2c6f52a6c6d1afed52b8b5e781fbc112ec545c1bf150e5281a464`
- camera_lock.py: `fc6295a84837a6fe7fc2a530430d3a20f6187ad48a343241c0e5f6a170c97415`
- burst_capture.py: `8d70515bdf266d8342c42ab13e782331c1fbe566cbd6d60ec1b021c8a4be4ce3`
- analyze_frames.py: `b1e90549dd0151ccc61e3b970cd128dacb0b4583f5170ff94f910e2cd0389e05`
- capture_publish.py: `4b50882ab97099c3c84222c6ffb63207996c0769a10500bc8be9d967d6c9924b`
- publish_github.py: `96a9d7b9ed0e1c5ea5b46f02a214f601bfd02ac280d0851e7de4ec629cac5b85`
- upload_frames.py: `67afd03846c22792177ca6095d41980c6290f66c6a8773516167fcabb09f95de`

After UTF-8 BOM/newline normalization, six of these seven installed sources
match the staging repository. Installed burst_capture.py differs materially:
it lacks the newer optional `attempts` argument and emitted
`capture_attempts` telemetry. Bounded two-attempt retry remains installed.
Repository tests are therefore not treated as installed telemetry acceptance.
No deployment or attempt-telemetry correction was made.

### Demonstrated behavior and explicit test scope

| Check | Result and scope |
|---|---|
| Existing Windows-host fixture suite | 72 cases attempted in 168.036 seconds: 67 passed, 1 failed, 4 errors, 0 skipped. Acquisition/model calls were mocked; state publication used isolated Git fixtures. Includes the 64 outage combinations, UNKNOWN/no-clean-negative admission, new-fault review gating, frozen forecast/alert contracts, nine-PM boundary gates and interrupted-state recovery. This was a selected acceptance suite, not a rerun of all 510 tests. |
| Five PowerShell entry-point cases | PowerShell 7/pwsh is absent. The five existing tests were attempted with only the executable name substituted in memory to installed Windows PowerShell 5.1. All five failed to establish acceptance (four JSON-output errors, one exit-code failure). Independent direct invocation confirmed PSSecurityException: .ps1 execution is disabled. No execution-policy change/bypass or installation was made; these five cases remain BLOCKED, not passed. |
| Direct Python read-only verifier | At 18:40:04 UTC, actual task inventory and heartbeat PASS; near-live six-frame evidence PASS; canonical status/burst/vision coherent and fresh PASS; four camera rows PASS and E2 back-deck/E3 rows FAIL. Overall FAIL describes the real partial canonical capture. Complete-capture-dependent R2/Git/archive checks are NOT_VERIFIED, not inferred successful. The Python entry point remains usable independently of the blocked PowerShell wrapper. |
| Installed capture failure/recovery fixture | Four tests passed against installed burst_capture.py: single-feed, all Montrose, all-six failure, and sequential failure then all-six-success for each failure scope. Real installed capture-loop/retry and publication-payload logic ran with mocked acquisition in isolated paths. Only assertions for absent newer attempt telemetry were omitted, explicitly; all health/media/retry assertions were retained. Failed images were excluded/deleted in payloads; healthy cameras continued; recovery restored successful payloads. No actual cloud upload was performed by these fixtures. |
| Installed Windows timeout | Installed capture_service.execute ran a disposable parent and child process, timed out at 3 seconds, invoked actual taskkill /T /F, returned failure, and the descendant was confirmed absent. Total measured check 3.41 seconds. A subsequent disposable successful child completed through the same execute function. Production main() was never started or stopped. |
| Installed device-lock release | Installed camera_lock.serialized released its real socket after an injected exception; a subsequent call using the same synthetic acceptance-only device succeeded. No real camera's lock was acquired. |
| Local network failure/recovery | A disposable child failed connecting to localhost port 1; installed execute returned failure; its next successful fixture completed. This does not establish remote network/API recovery. |
| Credential/API boundaries | Installed load_credentials rejected an absent fixture configuration. Installed refresh_access_token rejected a real loopback HTTP 401 and accepted a following loopback HTTP 200 with dummy credentials. Only the HTTP destination was redirected in the fixture. No real credentials were changed, read for these calls, revoked or submitted. Remote OAuth/API recovery remains NOT_VERIFIED. |
| Browser restart fixture | Two disposable installed Chrome/Playwright headless sessions started, rendered local fixture HTML, and closed successfully. No stream was opened. Recovery from a crashed production browser remains NOT_VERIFIED. |
| Retained archive | All 19 objects named in local capture_manifest.json for capture 20261010T130600741818-1ae990100430 matched their SHA256 values, including 12 healthy burst frames and three product JSONs. Failed-camera media was absent from that retained archive. This is local readback, not an R2 GET restore receipt. |

Reproducible host staging evidence is under
`C:\Users\ben_t\Documents\Codex\jubilee_pr74_acceptance_20261010`:
`run_acceptance.py`, `windows_tests.log`, `acceptance_results.json`,
`installed_capture_check.py`, `installed_capture_tests.log`,
`installed_capture_results.json`, `compare_runtime.py`,
`boundary_check.py`, `boundary_results.json`, and the pinned staging checkout.
The combined runner's exit code 0 is not a test-pass signal: its JSON/log reports
the five PowerShell failures explicitly.

### Naturally occurring partial outage and publication readback

The earlier 10:06 healthy-camera observation is historical. The newer canonical
capture is `2026-10-10T13:06:00.741818-05:00`: four cameras succeeded with
three frames; `pcl_e2_back_deck` and `pcl_e3_bay_mouth` failed.
Status, burst and vision capture identities match. Both failed vision rows have
`status=burst_not_ok` and no overall/temporal biological signal, rather than
a quiet classification. Healthy raw `none` values still are not confirmed
non-event labels. GitHub status blob `62a6b3c3b5e0c719340d31349d4e8829ae8508a3`
and vision blob `2d8d0cc1a57a7bdcb9416f7b8fd9074ef1fa5786` were read back.
The coordinator log records append-only publication
`1f5cb25033bdaf9cb61987503a76ac8b80d8f947` and successful pipeline completion
at 13:10:17 CDT despite that partial capture. Logs show near-live publication
returned to 6/6 at 13:21:06 CDT and remained 6/6 through 13:36:01.
Near-live recovery does not establish canonical six-camera recovery.
No extra canonical capture/model call was forced to replace the 13:06 record.

### Remaining gates

1. Five PowerShell wrapper cases require a permitted Windows script execution
   environment and an explicitly recorded interpreter. Host policy was preserved.
2. Canonical recovery on the next existing scheduled cycle and real partial/
   complete-outage R2/GitHub end-to-end readback remain unverified. Staging
   payload success and near-live recovery must not be counted as that receipt.
3. Genuine remote credential, vision-API, network and crashed-browser recovery
   remain unverified; local HTTP/browser fixtures have the narrower scope above.
4. Scheduler/service restart after actual power interruption, exhaustive process
   attribution and delivered freshness/material-fault notifications remain
   unverified. No reboot, production process termination or notification was
   induced. The existing 9 p.m. notification policy was not changed.
5. Installed attempt-telemetry drift is recorded for the existing Sensing owner;
   deployment/reconciliation is separate from this acceptance run.

Production runtime files, tasks/triggers, camera coverage, probabilities,
weights, thresholds, alerts, nine-PM policy and forecast binding were preserved.
No deliberate production outage, extra camera acquisition, paid AI request,
new scheduler/coordinator or scientific promotion occurred.

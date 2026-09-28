# Read-only desktop acceptance

Run the existing preflight from a reviewed repository checkout on PointClearPC:

```powershell
& .\tools\desktop_preflight.ps1 -Root 'C:\JubileeCams'
```

Use `-Python 'C:\path\to\python.exe'` if Python is not on PATH. The reviewed
`tools/desktop_verify.py`, `desktop_runtime/archive_integrity.py`,
`camera_policy.py`, and `seasonal_policy.py` must be present in that checkout.
Use the desktop's existing Python with Pillow and, for R2, boto3; Windows also
needs the existing IANA timezone data (`tzdata`). The script does not install
anything, replace deployed files, start a camera, invoke capture/analyze/upload/
publish entry points, change a task, or create another runtime.

One sanitized JSON report goes to stdout. There are no report files, temporary
restores, Python bytecode caches, Git fetches, index refreshes, ref updates,
commits, pushes, or object-store writes. The default network operations are
read-only Git `ls-remote` and R2 `GetObject`. `-Offline` disables both and does not
read `r2.json`; offline mode cannot produce overall PASS. Saving stdout is an
explicit caller action, outside this check.

## Results and evidence

| Check | Acceptance evidence |
| --- | --- |
| Scheduled tasks | Exactly one running `Jubilee Live Cameras` coordinator with a recognized Python action for the canonical root; enabled state, last result, missed runs, valid last-run time; other Jubilee/capture tasks disabled; fresh coordinator heartbeat and successful live/canonical timestamps. A long-running task may have an old start time; `0x41301` means running, not failed. |
| Near-live | Its independent status timestamp, all six successful camera timestamps, JPEG sizes and decoding; product bytes unchanged while inspected. Near-live and canonical timestamps are not required to match. |
| Canonical identity | Fresh timezone-aware `capture_time_ct`, identical across status/burst/vision; exactly the six policy cameras; agreement of optional capture IDs. |
| Six camera results | Successful status/burst/vision, three ordered shots, fresh increasing timestamps and actual/nominal timing labels, vision shot identity, byte counts, JPEG decode, latest image equal to shot three. Every camera receives a result even if another fails. |
| Local archive | Recompute the existing `freeze()` capture ID and all 27 hashes from canonical metadata + six latest images + 18 burst frames. Compare the existing `captures/<capture_id>/capture_manifest.json` and every archived byte. No call to `freeze()` and no new manifest. |
| Git publication | Latest bounded-tail coordinator success receipt (or explicit commit), exactly one parent matching prior-main evidence, whole-tree changes confined to the publisher allowlist, all nine published metadata/latest-image files equal to this capture, parent and publication ancestors of current remote main. Read remote main again to detect concurrent movement. |
| R2 archive | Use local `r2.json` credentials only in memory. Read the current pointer; require matching identity, local hashes, six camera records, 18 shot records and exactly the uploader's expected hash keys. Use `VerifiedStore.read_verified()` from `archive_integrity.py` to GET/hash/decode the 30 expected objects, including the immutable manifest and current status. Re-read the pointer. Burst restores stay in memory. |
| Snapshot stability | Re-read inspected canonical bytes after all checks. A changing snapshot invalidates capture/archive/publication acceptance instead of passing a mixture of cycles. |

Canonical freshness is the existing publisher/archive limit of 60 minutes with
two minutes of future-clock tolerance. Heartbeat and near-live limits are 25
minutes because the single serialized service may spend 900 seconds in the
canonical pipeline, 300 in live capture and 90 in live upload before its next
heartbeat. Outside May 18–November 14, task health checks the truthful seasonal
pause; an old canonical capture still cannot receive fresh-capture acceptance.

Exit codes: **0 PASS**, **1 FAIL**, **2 NOT_VERIFIED**. Overall PASS requires every
check and every camera to pass. A confirmed failure takes precedence over an
unavailable check. Missing files, unavailable Task Scheduler, missing R2
credentials/dependencies/permissions, unavailable Git objects/history, and
concurrent updates cannot count as verified. Historical manifests without
original hashes do not establish original integrity.

R2 keys are derived from this validated capture, never arbitrary paths in a
manifest. The configured endpoint must be HTTPS on Cloudflare's R2 storage
domain. GET calls have bounded connect/read timeouts and one attempt. Neither
credentials, endpoint/bucket, signed URLs, task command lines/principals, local
paths, arbitrary camera text nor raw exception/SDK/Git diagnostics enter the
report. No Google credentials or camera inventory are read.

## Git evidence limitations

The publisher already leaves a success SHA in `capture_service.log` and its
fetched parent in `.git/FETCH_HEAD`. The checker uses these existing receipts.
If another fetch has replaced FETCH_HEAD, supply a **known prior-main SHA**
from the relevant publication evidence:

```powershell
& .\tools\desktop_preflight.ps1 -Root 'C:\JubileeCams' `
  -PublishedCommit '<40-character-publication-SHA>' `
  -PreviousMain '<40-character-parent-that-was-main>'
```

These values are evidence inputs, not instructions to move refs. An arbitrary
ancestor is not sufficient: the prior main must equal the publication's direct
parent. Subsequent unrelated main commits are allowed. If current remote main
is absent from the local object database, the result is NOT_VERIFIED; the check
will not fetch to fill the gap. The remote must be the canonical HTTPS GitHub
repository. Credential helpers and interactive authentication are disabled.

This checks the observed publication contract; it cannot reconstruct every
historical force push or prove that the source file currently on disk was the
one executed earlier. Stable file comparisons are a point-in-time observation,
not a filesystem transaction. Run after an existing scheduled cycle has
completed; a cycle in progress can legitimately be incomplete. Re-running this
check is safe and never triggers a cycle.

## Scope of tests versus desktop evidence

`python -B -m unittest discover -s tests -p 'test_*.py' -v` exercises offline
fixtures, real JPEG decoding and local Git history. CI also runs the actual
PowerShell wrapper on Windows with stubbed Task Scheduler data. No CI job uses
production credentials or contacts the cameras/R2.

Passing these tests remains **offline_regressions_not_desktop_end_to_end**.
Neither `upgrade_readiness.json`, `sensing_audit.json`, nor old acceptance
receipts are upgraded by this change. Only a current report produced on the
actual desktop can establish current desktop acceptance. Source changes in
this PR are not deployment or proof that PointClearPC has passed.

Task Scheduler status reference:
https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-error-and-success-constants

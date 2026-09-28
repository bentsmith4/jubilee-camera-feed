# PCL E3 single-cycle capture failure, September 28, 2026

## Finding and limits

The post-deployment sequence supports an isolated, self-recovering capture failure,
not a demonstrated persistent camera or cadence defect. The exact upstream cause
is UNKNOWN: the public failure contains only a CalledProcessError, without its
return code, stderr category or attempt history. Do not relabel it as a confirmed
503, timeout, authorization failure, or failed retry based on timing alone.

The legacy ID `pcl_e3_bay_mouth` is Point Clear Landing House Deck, an RTSP camera.
`SIX_CAMERA_POLICY.md` remains authoritative for equal six-camera treatment.

## Committed production evidence

All times are September 28, America/Chicago (UTC-05:00). Successful E3 shots are
nominal ten-second intervals from one stream, not independently clocked frames.
Every row below contains all six expected camera identities.

| Canonical burst | Commit | E3 result | Other five |
|---|---|---|---|
| 11:06:04.287538 | `6523405b3bfc1be2a9207722248c1267f133f008` | Three shots, ending 11:08:55.231708 | All OK |
| 12:06:05.006137 | `72d9d4b949fa43dc749d7afcfdbc6604079da96c` | Three shots, ending 12:09:28.271401 | All OK |
| 13:06:02.286476 | `e9b8bc0` | Three shots, ending 13:08:48.561010 | All OK |
| 14:06:03.671382 | `d472301` | Three shots, ending 14:08:43.098554 | All OK |
| 15:06:05.189776 | `ddc75d18e67b366800789b923420fa3b73aa4211` | Failed at 15:08:51.548645; no admitted shots | All OK |
| 16:06:01.156579 | `70715f2d62fa0fc3bd1f3b6094f81039d1990d14` | Three shots, ending 16:08:39.745363 | All OK |
| 17:06:01.739815 | `6e74b53` | Three shots, ending 17:08:43.515822 | All OK |

Sources: `status.json`, `burst_status.json` and `vision.json` at the failed and
recovery commits; `burst_status.json` at the preceding commits. The failed E3
vision row is `burst_not_ok`, not a fabricated biological negative. The failure
commit removes the E3 latest JPEG; recovery republishes it.

- Freshness run [36481162309](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36481162309),
  reconcile job 109129077336: at 20:53:53.6578463Z,
  `REVIEW_REQUIRED: changed camera failures need material-fault assessment`.
- Freshness run [36483218827](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36483218827),
  reconcile job 109133705463: same guard at 21:02:55.8171128Z.
- Recovery run [36484360728](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/36484360728):
  regression, reconcile and current-state-status all succeeded. Reconcile job
  109139252655 reported `already_current` at 21:19:34.4672103Z, evidence commit
  `0d997e6557f761a4f7d72fc25b4cebe11db45bb1`. It did not create another repair.
  Status job 109140772697 checked the 16:14:23.986400 CT snapshot at age 7.778 minutes.

These guards correctly retained the need for explicit material-fault assessment
while the failure set differed. Recovery must not be used to weaken that guard.

## Capture path and existing mitigation

Reviewed `burst_capture.py` dispatches RTSP through `GenerateRtspStream`, FFmpeg
(TCP, 60-second subprocess timeout, three frames at nominal ten-second spacing),
and `StopRtspStream` in `finally` when an extension token is supplied. The camera
wrapper already permits two attempts, separated by eight seconds, and clears
partial images before each attempt. Each retry requests a new stream. Other
cameras continue after exhaustion; failure stays `ok=false`.

PR #15 previously added bounded, local-only FFmpeg categories and numeric exit
codes, without retaining stderr, URLs or credentials. Its description records
prior RTSP failures on both E2 and E3; that does not establish this incident's
cause. This session cannot read the PointClearPC diagnostic files. The #26
cadence deployment receipt replaced only `capture_service.py`; it does not
attest to the exact deployed bytes or retry execution of `burst_capture.py`.

## Focused diagnostic change

Add `capture_attempts` to each attempted camera's canonical status and burst
metadata. Each record contains only attempt number, success flag and, on failure,
a fixed category plus numeric return code or HTTP status where available. Preserve
both a failed first attempt and a successful retry. Process timeout is separate
from an FFmpeg error exit; unrecognized errors remain unclassified. Missing
inventory cameras retain their existing unavailable status without invented
attempts. Capture-attempt success does not override later frame-copy/status
failure; camera-level `ok` remains authoritative.

No raw exception strings, stderr, command arguments, device resource IDs, signed
URLs, credentials or local diagnostic files are newly published. The existing
sanitized `error` field remains unchanged. This is additive telemetry, not a
claim to repair the unknown upstream fault.

Retry counts/waits, stream cleanup, success/failure handling, six-camera policy,
canonical cadence, probabilities, weights, UNKNOWN semantics and alert thresholds
are unchanged. No model or production-state file is edited.

## Validation and deployment boundary

Offline regressions exercise both-attempt failure, second-attempt recovery,
partial-frame cleanup, generation/cleanup of both RTSP sessions, equal retry
handling for all six IDs, a production-shaped E3 failure with five successes,
public-payload behavior, and exclusion of secrets from diagnostic records.

A repository merge does not install runtime code. Deploy the reviewed
`capture_diagnostics.py` and `burst_capture.py` together on PointClearPC only
after comparing local versions, preserving any local divergence, backing up,
and waiting for current capture children to finish. Use the existing coordinator;
no duplicate tasks or manual diagnostic capture is needed. Do not replace
`refresh_all.py`, credentials, camera configuration, R2 configuration, private
frames/ROIs, or other runtime files. Confirm the new fields on the next ordinary
scheduled publication. This investigation does not claim that deployment or
live diagnostic acceptance has occurred.

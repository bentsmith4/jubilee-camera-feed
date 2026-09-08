Current owner policy: all six cameras have equal capture, vision and public-feed/archive treatment. See `../SIX_CAMERA_POLICY.md`. The earlier private-only statements below describe the first deployment and are superseded.

# Desktop runtime, September 6, 2026

Operational home: `C:\JubileeCams`. These are reviewed copies of deployed runtime files, not a second service installation. Keep `go2rtc.yaml`, `r2.json`, Google device resource IDs, private camera frames, and private ROI files outside this public repository.

The existing `refresh_all.py` remains local because it owns the authenticated Google client. Its camera-name map now recognizes `Boat Camera` as `montrose_pier_boat`, retaining the old `Pier Boat camera` alias. The new shoreline camera is intentionally absent from this public map. `private_capture.py` independently dispatches by actual supportedProtocols and stores only local private bursts.

`live_loop.py` is the compatibility entry point for `capture_service.py`. One existing Windows job owns the serialized live/hourly/dawn queue. The old dawn and unattended-test jobs are disabled, not deleted. Hourly cadence remains :06 and dawn bursts remain civil dawn +/- two hours at twenty-minute slots. The shared per-device lock also protects manual capture clients using the deployed capture functions.

The Git publisher creates an allowlisted tree with an up-to-date remote parent and normal push. It never resets the working checkout, amends a commit, publishes config/model files, or force-pushes. Concurrent updates retry at most three times. A separate temporary Git index preserves staged/uncommitted work. R2 remains the primary media archive; no retention rules were changed.

Archive publication validates a coherent snapshot, stores an immutable local capture directory, uploads and reads each object back for SHA256 verification, then advances the archive pointer last. Historical manifests lack original hashes; restore tests verify sizes and JPEG decoding and record hashes now. No historical integrity claim is fabricated.

The descriptive anonymous human-observation fields do not alter production forecast weights or alligator alert thresholds. The shoreline originals never enter the public uploader or remote vision API. Local ROI metadata is approximate and does not itself mask pixels; no external derivative is produced.

Rollback: `C:\JubileeCams\rollback_20260906_desktop_upgrade` contains original files, configuration, Git history, and task XML. To undo only coordination, stop the live job, restore `live_loop_before_coordinator.py` as `live_loop.py`, re-enable Dawn Cameras, and start the live job. Do not restore the old unsafe Git publisher to active use.

Remaining: public-camera recording rights/access, R2 lifecycle-read permission, surveyed shoreline calibration, and ChatGPT schedule changes. Windows automatic restart settings were rejected and remain unchanged. Both the pre-switch 17:06 scheduled pipeline and a post-switch coordinator canonical pipeline completed successfully; the coordinator then resumed live publication.


## September 8 seasonal and efficiency update
Source changes are not desktop deployment. The publisher fetches remote Git history to append camera results; it does not install desktop scripts.

Install these five files from one reviewed commit together after backing up current files: seasonal_policy.py (new helper first), analyze_frames.py, capture_publish.py, scheduler_router.py, capture_service.py. Stop the existing coordinator/canonical jobs and wait for child processes to finish before replacement, then restart the same existing jobs. Do not create duplicate scheduled jobs, reset the camera repository, or replace local credentials/configuration/refresh_all.py. If current local files differ from their reviewed pre-update versions, reconcile those differences before replacement. Keep the backup for rollback of these five files only.

Operating window: May 18–November 14 inclusive, America/Chicago. The coordinator preserves independent live refresh but skips canonical capture/paid analysis outside this window and records offseason_not_monitored. The canonical pipeline's embedded alligator analysis and alerts also pause. Off-season is not a biological negative. The helper rechecks before each API request and pipeline stage.

In-season coverage/model/image detail remain unchanged. Prompts compact embedded JSON; camera prompts now receive shot timestamps with actual/nominal labels; synthesis uses nominal ten-second spacing and does not assume simultaneous cameras. Local frames/api_usage.jsonl records token usage, including cached input and reasoning output counts when returned, without prompt/image/response content. Token counters are not dollar charges and require billing reconciliation.

Deployment acceptance: require runtime_version=2026-09-08-season-efficiency-timing-v1 in a newly captured vision.json, matching capture IDs across status/burst/vision, six successful three-frame results, coherent timing and functioning local usage telemetry. Check the coordinator state is truthful. Do not claim measured savings or installed seasonal shutdown until these checks pass.

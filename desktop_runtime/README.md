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

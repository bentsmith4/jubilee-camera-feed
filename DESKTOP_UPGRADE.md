Execution update: desktop work has now been applied and tested; see `DESKTOP_EXECUTION_REPORT.md` for actual results and remaining access/rights blocks. The handoff below records the original acceptance requirements, not the current deployment status.

# Jubilee desktop upgrade: start here

Owner authorization: Ben requested the coordinated camera/model consolidation on September 6, 2026 and reports a new Montrose shoreline camera in his Google account.

## Boundary and current status

The operational home remains `C:\JubileeCams`. This repository is its public code/status mirror. Do not create another project home. Repository code changes and GitHub tests are not proof that Windows capture jobs or ChatGPT automations changed. The current chat cannot operate the desktop, call Google SDM using local credentials, or modify ChatGPT tasks. This is the handoff for the local Work/Codex session with access to the actual runtime.

Read `model_data/upgrade_readiness.json`, `camera_sources.json`, `sensing_audit.json`, `data_retention_policy.json`, `operations_contract.json` and `sensing_and_science_architecture.md`. Read existing local capture and publication code before editing. Record file hashes, task settings and a rollback copy in the existing project. Preserve credentials locally; never paste them into chat, logs, issue bodies, commits or this public repository.

## 1. Restore and onboard the private cameras

1. Run the read-only `tools/desktop_preflight.ps1`. Inspect `burst_capture.py`, `capture_publish.py`, `upload_frames.py`, `live_capture.py`, `live_upload.py`, `dawn_runner.py`, the actual Google authentication module and configured device mapping.
2. Diagnose why `montrose_pier_boat` is omitted from current capture status and appears as `burst_not_ok` in vision. Do not guess the cause. Check permissions, supported protocol, executable paths and bounded stream startup separately. A historic WinError2 was reported but is not proof of the current failure.
3. Use the existing authenticated Google SDM client to list permitted devices. Read `sdm.devices.traits.Info.customName`, room relations and `CameraLiveStream.supportedProtocols`. Resolve the NEW shoreline-facing Montrose device by the actual account inventory and a locally inspected frame. `montrose_shoreline` is only a provisional internal ID, not a Google name or device-resource ID.
4. If the new device is absent, use Google's existing Partner Connections Manager to grant access to that camera, then repeat inventory. Do not ask Ben for passwords/tokens. Account visibility in Google Home does not prove SDM permission.
5. Google Home migrations can change RTSP to WEB_RTC. Dispatch by the reported protocol, not model/name. Reuse the proven working WebRTC implementation. Respect five-minute sessions; close/stop streams and handle extension only where required. A single RTSP URL cannot be shared between different clients.
6. BEFORE adding the new device to any publication loop, enforce `private_only`: original frames, identifying features, device IDs and signed URLs remain in local/private storage. Mask homes/interiors and unrelated private areas; no face recognition or person identity tracking. Verify the uploader has an explicit allowlist, not 'upload every discovered image'. Preserve existing cameras' publication policy unless Ben approves changing it.
7. Frame and calibrate the nearshore region: waterline, wet beach, pilings, fish-light area and relevant shoreline. Store ROI polygons, approximate visible shoreline length, orientation and camera height when measurable. Keep unknowns unknown. Group all Montrose views as one correlated site until surveyed evidence supports otherwise.
8. Success means actual fresh pixels from every intended device, valid timestamps, correct ROI, privacy filtering, and a recoverable archived burst—not an entry in a registry.

## 2. One capture service, separate products

The 0/10/20-second three-frame burst already exists; preserve it unless a measured experiment justifies changing it. The live single-frame directory must stay distinct from canonical bursts. Do not substitute a live frame into an earlier burst.

Introduce one per-device acquisition lock and a bounded work queue. Live and dawn/hourly jobs must not contend for the same stream. Use one stream for each temporal sequence. Serialize requests to the same device and use bounded parallelism across devices. Always release locks on failure; test timeout/recovery. Use backoff and circuit-breaker states without removing failed cameras from the expected inventory.

Create immutable `capture_id` directories. Match status, burst, vision and image hashes to that ID. Publish an archive manifest only after all required objects pass verification; publish the latest pointer last. A failed camera is an explicit record with reason and last-success time. Never advertise a stale JPG as current.

Compare the actual generated vision schema against `people_present`, `flashlight_activity`, `motion_pattern`, `clustered_search_behavior`, `temporal_persistence`, `human_sensor_score`, confidence and detectability. The repository's September 6 outputs did not include those new fields despite the README describing them. Schema additions are not implementation until populated and validated. Searching lights remain a weak precursor, not Jubilee confirmation.

Cheap checks first: decodability, black/loading frames, blur/glare, source-time/PTS validation and repeated-frame hashes. Then ROI-focused vision. Do not infer biological inactivity from darkness, a poor angle or absence of a model detection. Keep a deterministic baseline capture sample even on low-risk days so adaptive sampling cannot destroy valid controls.

## 3. Public cameras: access, rights and physical coverage gates

Use `model_data/camera_sources.json`; it is a discovery registry, not a claim that streams are operational. Start with the official Fairhope Municipal Pier viewer. Inspect its actual embed and supported access method. Verify which beach segment is visible; a pier panorama does not automatically cover the location 300 yards north of the pier.

Hazcams/WXLOGIC explicitly restricts use/reproduction/distribution of media without prior written consent. Grand Hotel and AWN/Hazcams mirrors are therefore BLOCKED for automated recording until rights are established. Do not bypass a player, login, DRM, signed authorization or an express restriction. Mark the gap plainly. Use authorized alternatives where available rather than counting the blocked camera.

FOX10 Battleship and Dauphin Island viewers are context candidates. Verify source freshness, viewing geometry and permitted retention before enabling automated capture. A historic Daphne/Delta link must be checked for current operation. Do not equate Delta coverage with May Day/Village Point.

Deduplicate physical cameras across city/media/aggregator rebroadcasts. Each adapter must return either a validated capture record, a rights/access block, or an explicit failure. A webpage response or a player thumbnail is never live evidence.

## 4. Consolidate jobs without creating a coverage hole

Inventory BOTH Windows Task Scheduler and ChatGPT automations. They are different schedulers. Preserve working jobs until replacements pass tests. One owner per output and one writer per canonical file; use atomic writes and locks.

The approved four logical responsibilities are:
- Sensing & Alerting: acquire/QC current environmental and camera state; deduplicated contemporaneous report intake; bounded same-day evidence updates; no model-weight changes.
- Dawn Forecast: consume the latest versioned snapshot, selectively refresh stale critical inputs, use the frozen approved model, emit separate Point Clear and Daphne opportunity outputs plus intermediate cells and uncertainty.
- Dawn Timing: civil-dawn scheduling only.
- Model Research & Calibration: source discovery, historical ingest, events/observed controls, blocked validation, versioned model promotion and rollback.

Use `operations_contract.json` for the proposed responsibilities. Apply changes to existing ChatGPT task identities only when the session actually has task-management tools. Otherwise leave the scheduler state unchanged and label it NOT_APPLIED. Never claim that committing a JSON contract consolidated the actual tasks. End the temporary weekend sprint only after its acceptance report exists; don't disable unfinished work merely because Sunday ended.

Retain current alert threshold. Avoid duplicated dawn and hourly notifications by event/cell/model-version ID. Include daytime retrospective report reconciliation within sensing rather than reviving a redundant Day Verification task. Preserve silence on routine healthy runs and surface persistent health degradation separately from Jubilee alerts.

## 5. Retention and calibration integrity

An R2 burst archive was implemented earlier; verify it rather than claiming it never existed. Read `archive/latest_manifest.json` privately, validate a recent capture ID and download/check all three frames and hashes. Verify a prior-day and a prior-week archive as restore tests. Inspect R2 lifecycle and public/private exposure; do not delete or change lifecycle policies without an explicit reviewed plan.

Follow `data_retention_policy.json`: immutable raw public sensor responses and provenance; private camera originals in private storage; keep event windows AND preselected non-event-control windows. Preserve feature schema/model versions, forecast issue time, available-at timestamps, verification outcome, observation effort and detection quality. Keep acquisition time, event time and post time separate.

The corrected water-quality diagnostic excludes event-day samples, reports unique rows separately from repeated lag memberships, requires explicit event/station matching and does not call unreported dates true negatives. It cannot establish predictive performance. The earlier bacteria conclusion is superseded by INSUFFICIENT_VALIDATION. No production predictor gains weight from this diagnostic.

## 6. Acceptance tests and final report

Run the repository regression suite, then local integration tests: each intended Google camera, one allowed public adapter when available, missing-camera failure, stream contention, stale/future timestamps, failed upload, restart, task trigger, schema mismatch and archive restore. Test source-error pages and missing environmental measurements. No probabilities are manufactured when inputs conflict.

Report separately: (A) changed and tested in repository, (B) changed and tested on desktop, (C) ChatGPT task changes actually applied, (D) public access/rights blocks, (E) data actually ingested and archived with row counts, (F) forecast skill measured or still unknown. Give rollback paths and the next single owner action. Do not label the full upgrade operational while the new camera, public capture or archive validation remains untested.

## Official technical references

- Google protocol/session rules: https://developers.google.com/nest/device-access/traits/device/camera-live-stream
- Google permitted inventory: https://developers.google.com/nest/device-access/reference/rest/v1/enterprises.devices/list
- Google authorization: https://developers.google.com/nest/device-access/authorize
- Fairhope official viewer: https://www.fairhopeal.gov/visiting/piercam
- Public media terms: https://hazcams.com/
- USGS IV service: https://waterservices.usgs.gov/docs/instantaneous-values/instantaneous-values-details/
- Water Quality Portal services: https://www.waterqualitydata.us/webservices_documentation/

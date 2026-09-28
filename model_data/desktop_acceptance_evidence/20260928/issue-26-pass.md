Final status: PASS

Actual PointClearPC deployment and read-only acceptance receipt — 2026-09-28, 10:55–10:58 CDT (15:55–15:58 UTC). This supersedes this chat's earlier BLOCKED_LOCAL_DIVERGENCE receipt.

The owner authorized preserving the local recovery safeguards, reviewing/merging the repository fix, and retrying deployment. PR #29 is merged: https://github.com/bentsmith4/jubilee-camera-feed/pull/29
Reviewed main deployed: `d56f884596ab8709dfd78d57e5317784c2ea25d4`.
PR head: `26bb1b88638d0d7cb39454ba1d4ec42474636b81`.
Both required ancestry gates passed (`git merge-base --is-ancestor`, exit 0):
- cadence merge `257482cfe2c0e9f8890417bdb38e403b73bd3b1d`
- forecast-contract merge `1edd9e97ff7fff13216fee6237e482690ce9dae0`

The reviewed fix retains the deployed UTF-8 state loading, dictionary validation, recovery from OSError/UnicodeError/ValueError, and flush/fsync before atomic replacement. The cadence, 15-minute minimum spacing, seasonal behavior, and forecast/model contracts were not changed by this fix. All 268 GitHub runtime tests passed, all 5 Windows preflight-wrapper tests passed, and research offline-validation passed. Fourteen focused tests also passed locally; the broader local run had missing numpy/netCDF4 imports, so no production dependencies were installed and full regression validation came from CI.

Deployment:
- Recompared the deployed file: unchanged original SHA-256 `9d5a6d550afcc2b319839c12705940b6721b11c6d8d1d7f45ce9139b99efcd8e`. Its previously identified local safeguards are now preserved in reviewed source; no further divergence was found.
- Confirmed one intended coordinator and no active capture/analysis descendants immediately before stopping.
- Stopped ONLY Jubilee Live Cameras.
- Saved timestamped backup `C:\JubileeCams\capture_service.py.backup_20260928T155510755Z`; backup hash matches the original above.
- Replaced ONLY `C:\JubileeCams\capture_service.py` with exact reviewed-main bytes.
- Deployed/source SHA-256 MATCH: `2598aa3eb1e2c6f52a6c6d1afed52b8b5e781fbc112ec545c1bf150e5281a464`.
- Restarted the SAME task at 10:55:10 CDT; task XML before/after was identical. No task was created, enabled, disabled or reconfigured.
- Fresh coordinator heartbeat and ordinary near-live operation resumed; legacy canonical slot migrated without a duplicate canonical capture.

Acceptance used the unmodified reviewed command:
```powershell
& .\tools\desktop_preflight.ps1 -Root 'C:\JubileeCams' -Python 'C:\Users\ben_t\AppData\Local\Programs\Python\Python314\python.exe'
```

Git evidence detail: the first default invocation returned NOT_VERIFIED only because the production Git object database lacks the newly reviewed remote-main commit. The second invocation returned PASS, exit 0, with a process-only `GIT_ALTERNATE_OBJECT_DIRECTORIES` pointing to the separate reviewed checkout's authentic Git objects. This supplied missing ancestry evidence without altering the verifier, thresholds, production Git objects/config/refs/index, or publication state. Production control-file hashes and object-file count were unchanged; the temporary environment setting was restored. No production fetch was performed.

| Required item | Evidence |
|---|---|
| Exactly one capture owner | One enabled Jubilee Live Cameras coordinator; all 3 relevant tasks inventoried. One coordinator socket owner, new PID 21740 on port 47651. |
| Other capture tasks disabled | Jubilee Dawn Cameras and Jubilee Unattended Test both Disabled / enabled=false. |
| Current coordinator state | Running / enabled=true; task start 2026-09-28T15:55:10Z; last result 267009 / 0x41301; zero missed runs. |
| Fresh coordinator heartbeat | Advanced after restart to 2026-09-28T10:57:56.510759-05:00. Last live success 10:55:51.310827 CDT; canonical success remains 10:11:12.889696 CDT from the existing normal cycle. |
| Deployed hash match | True, full deployed/source SHA-256 above; verified again at final readback. |
| All six expected identities | Exact six-camera set agrees across status/burst/vision: montrose_pier_boat, montrose_pier_bird, montrose_shoreline, pcl_e2_back_deck, pcl_e2_bay_mouth, pcl_e3_bay_mouth. |
| Current six-camera capture/vision | All six PASS, three_frames_and_vision_verified, three ordered frames each (18 total). Capture 2026-09-28T10:06:34.804851-05:00, checked at 10:57:08.821369 CDT within the existing 60-minute freshness window. Complete shot/vision identities, byte counts, JPEG decode and latest-equals-third-shot passed. All six near-live frames also passed. |
| Local immutable archive/hash integrity | PASS, local_manifest_and_bytes_verified; all 27 objects. Capture ID 20260928T100634804851-7fec39d06d99. |
| Git publication ancestry | PASS, append_only_publication_verified. Publication 195c3f152093239df5eaea40d329db7f28e23a49 has direct parent/prior-main 98dd6e47572f76d66e6f10f51b05e82d63a410bd; both are ancestors of reviewed/current main d56f884596ab8709dfd78d57e5317784c2ea25d4. All nine metadata/latest-image files match; all ten changed paths are allowlisted; remote-main reread stable. |
| R2 read-back | PASS, r2_get_restore_verified; 30 objects including 18 immutable burst frames, GET/hash/decode checked. Restore destination memory_only; pointer reread stable. |
| Snapshot stability | PASS, capture_unchanged_during_check. |

Exact blocker: NONE for this deployment and bounded read-only acceptance. The default verifier alone still needs current remote Git objects in its evidence view, as explicitly documented above. Acceptance used the already-completed normal canonical cycle, not a newly forced cycle or a claim that the next dawn has been observed.

Desktop changes made: YES — only the authorized capture_service.py replacement, timestamped backup, and stop/restart of the existing coordinator. No manual capture_publish.py, dawn_runner.py, or camera capture was invoked. No edits to refresh_all.py, credentials, camera config, r2.json, private frames/ROIs, unrelated runtime source, model probabilities/weights/thresholds, or production model state. No manual R2/publication writes or task-definition changes. The existing coordinator resumed its normal scheduled work.

One final execution receipt posted for this approved retry. Issue #26 intentionally remains open.

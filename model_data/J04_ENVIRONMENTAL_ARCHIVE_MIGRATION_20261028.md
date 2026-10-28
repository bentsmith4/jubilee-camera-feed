# J04 environmental archive: verified migration design and preparatory implementation

Status: **DESIGN_AND_OFFLINE_TOOLING_PREPARED / LIVE_MIGRATION_NOT_EXECUTED**.
Existing ownership: Sensing implements collection/publication; Research accepts scientific replay; Jubilee coordinates through MODEL_WORK_REGISTER.md. This extends J04, with no new scheduler, acquisition, alert surface, or work register. PR #141 recovery remains complete; storage migration remains open.

## Verified baseline and limits

Inspected main commit `0c5ac7647165d683bfbed0f2848356caca497232` (October 28, 2026). Exact Git-tree inventory: **3,902 compressed objects; 252,760,278 bytes; 247,239,722 bytes of remaining 500 MB headroom**. All 3,902 decompress and match the historical uncompressed SHA-256 embedded in their names. All 44 raw references in 12 current root-level manifests resolve and match their declared hashes. Summary: `j04_archive_migration_preflight_20261028.json`.

This advances the PR #141 recovery snapshot of 251,053,885 bytes. These are decimal bytes, not MiB. Neither snapshot predicts a reliable exhaustion date. Full reachable-history enumeration, old manifest versions, historic path variants and non-main branch archives have **not** been verified. A shallow current-tree inventory cannot establish historical completeness. The 500 MB guard measures public_archive file bytes, not total Git repository/history size. ARCOS currently stores 17,913 bytes in a separate raw_arcos_realtime path and is outside this guard.

| Archive class | Objects | Compressed bytes |
|---|---:|---:|
| ASOS | 752 | 1,079,883 |
| CO-OPS | 317 | 179,844 |
| USGS | 1,075 | 123,353,541 |
| NDBC / Weeks Bay | 454 | 15,621,820 |
| WQP | 13 | 437,364 |
| NGOFS2 Point Clear subset | 578 | 28,756,339 |
| NGOFS2 named-station subset | 464 | 77,948,175 |
| NGOFS2 shoreline-grid subset | 220 | 4,356,778 |
| Main Pass 2016 | 29 | 1,026,534 |
| **Total** | **3,902** | **252,760,278** |

The archive is mixed: original public responses plus generated NGOFS2 subsets. Preserve exactly what was retained; migration cannot recover full native NetCDF responses that were never archived. Do not relabel model subsets as raw observed data.

## Storage decision

**Preferred: a dedicated environmental R2 bucket in the existing account, with separate credentials and a production HTTPS read domain. Do not reuse or expose the camera bucket.** This reuses provider expertise without coupling public environmental access to camera security or retention. Bucket name/domain are proposals to provision, not resources asserted to exist.

Read-only PointClearPC inspection confirmed existing R2 endpoint configuration, credentials, camera bucket selection and a configured public_base. No values/secrets were copied. The existing credentials returned AccessDenied for both bucket enumeration and camera lifecycle inspection. These results do not establish the camera bucket's ACL, public reachability, environmental-bucket existence, retention or administrative rights. No camera settings were changed and no object writes occurred.

Cloudflare's current documentation supports conditional PutObject, bucket-scoped object credentials, and prefix bucket locks. Public production reads should use a custom domain; r2.dev is a rate-limited development endpoint. R2 bucket locks are managed through Cloudflare controls, not AWS S3 Object Lock headers. Administrators can remove lock rules; this is protection from routine writer errors, not an independent backup against account compromise.

| Arrangement | Decision / acceptance condition |
|---|---|
| Separate R2 bucket, same account | Preferred if an administrator can provision isolation, indefinite retention, reader access and bounded writer access, and tests below pass. |
| Existing camera bucket/prefix | Reject for this migration: unresolved access/lifecycle, shared credentials and risk of exposing camera media. |
| Separate S3-compatible archive | Fallback if R2 controls or access cannot be established in time. Must pass the same create-only/full-GET/hash/public-read/restore tests; no assumption that every S3-compatible service supports identical semantics. |
| Continued Git expansion or finite Actions artifacts | Neither is durable remediation. Preserve existing Git history; 30/90-day artifacts are diagnostic buffers, not permanent archive acceptance. |

Prerequisites, owned by the existing storage administrator/Sensing executor:

1. Dedicated environmental bucket and explicit non-secret storage ID, endpoint/jurisdiction, public HTTPS origin. No camera object or device ID in it. Keep bucket private while backfill is verified; public domain activation is a separately reviewed configuration action.
2. Disable expiration rules for originals, catalogs, manifests, receipts and normalized replay products. Apply indefinite bucket locks to immutable prefixes and read back the resulting configuration. Test protection with retained harmless canary objects; never test deletion against historical observations.
3. Separate bucket-scoped writer and independent read-only verifier credentials. Use `JUBILEE_ENV_ACCESS_KEY_ID` / `JUBILEE_ENV_SECRET_ACCESS_KEY` in the existing trusted execution environment. Never copy r2.json or use camera credentials for this path. No admin token in Actions. If coarse R2 object-write permissions permit delete, enforce retention locks; do not claim the token alone prevents deletion.
4. Production read domain serves original gzip bytes with Content-Type application/gzip, without transparent content transformation or Content-Encoding decompression. Immutable keys may be cached; mutable pointers must not select evidence. Verify anonymous GET returns exactly the same bytes. CORS only if an actual browser consumer requires it.
5. Confirm billing/quota ownership and restore egress/operation capacity. No spending change was made. Pin a tested boto3/botocore pair with PutObject IfNoneMatch support in a separate migration dependency file before live execution. The standard-library inventory/tests need no cloud SDK.
6. Retain an independently administered backup/restore route for newly object-only history. The frozen Git baseline covers old data only. Select its destination under the same J04 storage work, verify it before deleting or reducing any protection; no new recurring service is required to copy through existing publication runs.

## Data and provenance contract

- Preserve original compressed bytes, historical raw SHA-256, filename/path, source manifest bytes, Git commit/blob identity and source timestamps. **Never recompress old objects.** Add compressed SHA-256 and byte counts as new integrity fields; do not replace the old hash.
- Object key: `environmental/v1/objects/<class>/<raw_sha256>/<compressed_sha256>.gz`. The extra compressed digest preserves different gzip representations of identical raw content. No mutable latest key is scientific evidence.
- Retain logical manifest raw_path/subset_archive/raw_archive values. Add a versioned archive reference/catalog containing storage ID, exact key, compressed/raw hashes and sizes. For old content retain Git blob and commit; future remote-only objects have typed object provenance, never fabricated Git blob IDs.
- Preserve manifest and normalized-product versions as exact bytes under separate content-addressed keys, with a per-run catalog binding all raw references, manifest hashes, normalized hashes, producer outcome, code commit and run identity. Object upload succeeds first; catalog upload and full GET second; Git manifest/reference commit last. Catalogs and receipts are immutable and sharded per producer/run to avoid competing append operations on a growing global file.
- Authoritative reference roots remain committed in Git. A self-reported object metadata hash, ETag, HEAD result, successful PUT or catalog presence alone never proves integrity. Verify full GET compressed SHA, decompression, raw SHA and size. Public read and independent read-only restore are separate gates.
- No current manifest or historical snapshot may resolve a remote reference from an unpinned latest catalog. Use the catalog hash committed with the evidence's input commit or explicit snapshot provenance. Retain legacy Git resolution for all old snapshots.

## Required integration changes (not activated by this preparatory patch)

| Component | Required change and invariant |
|---|---|
| environmental_archive_migration.py | Prepared now: pinned Git-tree inventory, original-byte mirror, conditional create, full GET verification, resumability, fresh-directory restoration. No workflow imports it yet. History-union inventory, manifest/catalog upload, public-reader verification and production cutover remain to implement. |
| ingest_asos_weather.py, ingest_noaa_water_level.py, ingest_river_forcing.py, ingest_weeks_bay_realtime.py, ingest_water_quality.py, ingest_griidc_main_pass_20160419.py, three ingest_ngofs2 scripts | Keep current acquisition/normalization/QC and logical paths; introduce one archive adapter for newly generated objects, with explicit legacy/mirror/object modes. Validate raw hashes even when a local path exists. Add compressed identity/reference only after verified durable upload. No source re-fetch for backfill. |
| stage_sensing_outputs.py | Keep producer outcome allowlists and NGOFS2 validation grouping. Admit manifests and new archive references only after all their required objects/catalog pass verification; isolate a failed storage/source group from independently valid groups. In object mode do not git-add new raw blobs. Preserve all already tracked baseline archive files and append-only checks. Calculate Git budget from tracked plus proposed staged archive bytes, separately reporting temporary workspace bytes and uncommitted evidence. |
| sensing_quality.yml and asos_weather.yml | Add adapter credentials/mode and verification steps within existing jobs and existing shared concurrency group. Preserve schedules, camera event triggers, cancellation policy and retry/rebase controls. Do not copy the complete legacy archive into every artifact after migration; retain current-run failure evidence and immutable receipt references. No production credentials on untrusted PR runs. |
| water_quality_ingest.yml | Its inline **250 MB hard stop is still present**, independent of PR #141. Replace with the same centralized policy and verified publication adapter when integrating. Its present guard cannot publish at the inspected 252.76 MB archive size. Preserve weekly schedule and diagnostic behavior. |
| resolve_sensing_publication_conflicts.py | Continue failing on manifest/archive conflicts; no broad ours/theirs overwrite. New immutable catalog paths must be distinct by run/content and remain tied to their producer. Retry rebase/push from clean worktree, preserving newer camera and registry state. |
| check_current_state_freshness.Reader | Add explicit verified object resolver for committed archive references. Legacy local/Git reads unchanged. Missing local bytes are not proof of storage failure; a corrupt local file is not silently ignored. Enforce exact compressed/raw hashes, bounded reads, path safety, HTTPS allowlist, timeouts and error classification. Never trust arbitrary manifest URLs or silently fall back to live source retrieval. |
| reconcile_current_state.CommittedReader, blob(), and source_provenance construction | Current code uses git show/cat-file and expects git_blob for every read, including compressed raw data. Update typed provenance to bind remote raw bytes and pinned catalog hashes. Resolve only committed evidence; no dirty workspace or latest object. Preserve strict forecast/snapshot binding and as-of/QC/UNKNOWN checks. A simple downloaded cache alone does not satisfy CommittedReader. |
| current_state_freshness.yml, forecast_consistency.yml and dependent replay tests | Include new reference/catalog paths in existing event filters where needed; hydrate through the verified resolver for offline validation/replay. Test legacy snapshots and remote-only commits. No duplicate freshness workflow. |
| build_readiness.py, data_retention_policy.json, run summaries | Report frozen Git bytes, remote verified bytes, migration phase, backup/restore state and failed transfers distinctly. Keep automatic_deletion_authorized=false, 250 MB advisory and 500 MB legacy hard ceiling; do not claim object-mode readiness while only mirror succeeds. |
| raw_arcos_realtime / arcos_realtime.yml | Separate existing layout outside public_archive; preserve its current behavior in this first migration. Inventory its history and adapt in a follow-up within J04 using its existing workflow, rather than accidentally declaring the whole environmental estate migrated. |

## Execution sequence and acceptance gates

1. **Prepare / current state (this patch).** Pin baseline; verify all current-tree raw bytes and references; publish this design, tests and bounded receipt through a draft J04 PR. Keep PR #141 recovery closed. Do not alter live schedules, scientific weights or archive settings.
2. **Provision and validate target.** Sensing/storage administrator supplies dedicated bucket/read origin and credential references; read back lifecycle/locks/access. Use harmless retained canaries to verify conditional writes, overwrite protection, exact GET, public/private separation, public cache behavior and read-only restore. Live administration is presently blocked by unavailable configuration privileges, not by a failed camera archive.
3. **Backfill exact historical union without acquisition.** In an isolated full-history checkout fetch the relevant refs. Enumerate `git rev-list --objects --all -- model_data/public_archive` plus historical source manifests/normalized products. Resolve every distinct path/blob version, including removed or replaced blobs; verify every raw digest; deduplicate only identical compressed bytes. Save source commits/refs and complete object-set digest. The included current-tree inventory is the first checkpoint, not this union gate. Copy original objects conditionally, re-GET every object, publish immutable catalogs/manifests and mirror receipts. Interruption resumes from verified objects, never overwrites. Any missing Git blob, unsupported archive class, decode/hash mismatch or incomplete history blocks a claim of full historical migration.
4. **Reader compatibility first.** Deploy reviewed backward-compatible resolver/provenance code in existing consumers while publication remains Git-based. Exercise old snapshots, exact historical manifests and remote-only fixture commits; verify forecasts and current reconciliation remain byte/semantically equivalent at identical issue time. A replay without network uses a separately verified hydrated archive/catalog cache.
5. **Mirror natural collection.** In the existing Sensing/ASOS/WQP workflows, mirror new admitted outputs while retaining normal Git publication. Keep exactly the same collection cadence. Verify at least one ordinary scheduled Sensing run and one camera-triggered ASOS run, WQP publication on its next normal cycle, all producer classes in scope, downstream freshness, missing-input UNKNOWN and no manifest-to-object gaps. Do not dispatch an extra full sensing run to manufacture acceptance.
6. **Freeze Git baseline and cut over future bytes.** After full backfill/restore and mirror acceptance, record the exact baseline set/commit and enable object mode through one reviewed change across writers/readers. Keep every existing tracked raw file; **no rm, git rm, filter-repo, force push or history rewrite**. New raw objects go to verified storage, with compact committed references/manifests; a producer's reference is published only after its durable payload/catalog is confirmed. Git archive bytes then stop growing without deleting history. This is actual capacity remediation; mirroring alone is not.
7. **Observe and close narrowly.** Verify unattended runs from each unchanged trigger and all participating source groups, independent cold restore and semantic replay, and no new raw Git growth. Record exact commits, runs, object/catalog hashes, reader version and restore results under J04. Close only the migrated public_archive scope; historical science acceptance, ARCOS and independent-backup gaps stay separately explicit.

## Integrity, failure and rollback matrix

| Test | Pass condition |
|---|---|
| Baseline and historical union | Every selected path/blob counted; original compressed bytes identical; gzip decode and old raw SHA match; all referenced objects present; no private/camera paths. Full-history completeness cannot be inferred from current tree. |
| Transfer and restart | No writes on AccessDenied or timeout. Conditional create races accept only a fully verified winner. Corrupt existing objects fail closed, never overwrite. Partial transfer issues no all-objects success receipt; rerun resumes safely. |
| Public and independent restore | Independent read-only GET and anonymous production-domain GET match compressed bytes for all backfilled objects; restore all baseline objects into a new empty directory and compare both hashes/counts. Replay current, prior-day, prior-week and oldest available manifests for each class. |
| Scientific equivalence | Identical raw-to-normalized rows, units, source/method/depth/datum, as-of time, QC, missingness and feature results; NGOFS2 remains MODEL with existing availability rejection. Preserve zero weights, UNKNOWN, forecast binding, 9 p.m. gate and alert policy. |
| Missing/corrupt/unavailable remote evidence | Exact source classified unavailable/UNKNOWN through existing material-input-fault route; no stale replacement or bogus negative. Independent valid source groups may publish. Never claim fresh acceptance from a success PUT alone. |
| Publication race | Upload success + failed Git push leaves harmless immutable objects, not dangling committed references. Retry same content keys; normal ancestry-checked rebase preserves concurrent updates. A later catalog cannot change an older snapshot's evidence. |
| Storage outage | Existing Git/local verified bytes remain readable. New raw stays in existing diagnostic artifacts and available runner state; do not falsely mark it durable. For prolonged failure before object-only cutover, use unchanged bounded Git path. After cutover, retain resolver and remote refs; restore missing new bytes and publish a verified bounded Git fallback only if headroom permits. At the cap fail closed and surface existing fault state; do not delete data or stop collection schedules. |
| Rollback | Before cutover revert mode to legacy with all original Git files untouched. After cutover do not revert to an old Git-only reader: retain compatible resolver, use verified recovery cache/backup or materialize exact referenced bytes in a reviewed Git commit within budget. Preserve every object, catalog and reference; no destructive cleanup. |

Migration deadline policy: measure per-run unique compressed growth over rolling 7/30 days in the existing summaries; calculate projected days to 500 MB using the larger observed daily rate and account for pending unpublished payloads. Until enough history is measured, exhaustion date is UNKNOWN. Proposed operational intervention: at 400 MB or less than 30 days projected headroom, escalate through existing Sensing fault/coordination policy. This proposal adds no recurring task and has not changed alert thresholds. Begin provisioning now; do not wait for that trigger.

## Preparatory CLI and reproducibility

Current-tree inventory (standard library; read-only Git access):

```bash
python model_data/environmental_archive_migration.py inventory \
  --ref 0c5ac7647165d683bfbed0f2848356caca497232 --out /tmp/j04-inventory.json
python -m unittest discover -s tests -p test_environmental_archive_migration.py -v
```

Expected inventory SHA-256: `afac47085927d02e460bab899fec1045bbfd48f9b38962fc4bf3723ae43dbbbb` (canonical newline-terminated JSON). Do not check a growing full inventory into Git every run; retain its immutable object/catalog and compact hash receipt. The CLI inventory file is generated, not a separate canonical ledger.

After target prerequisites and SDK compatibility pass, an authorized executor can run the prepared `mirror` command with explicit `--inventory`, `--inventory-sha256`, `--endpoint`, `--bucket`, matching `--confirm-environmental-bucket`, and a new `--receipt` path; the named environment variables supply credentials. `restore` takes the same pinned inventory plus `--destination` pointing to a non-existent directory and a new receipt. Never use the camera bucket. These commands currently operate on a complete pinned Git tree; they do not implement historical-union enumeration, catalog publication, production resolver or automatic cutover. A mirror receipt is not final migration acceptance.

## Sources

- Recovery and acceptance: https://github.com/bentsmith4/jubilee-camera-feed/pull/141
- Repository evidence anchored to `0c5ac7647165d683bfbed0f2848356caca497232`: data_retention_policy.json, stage_sensing_outputs.py, the existing workflows, check_current_state_freshness.py, reconcile_current_state.py, desktop_runtime/archive_integrity.py and upload_frames.py.
- Cloudflare public production access: https://developers.cloudflare.com/r2/buckets/public-buckets/
- Conditional S3 operations and compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- Bucket-scoped credentials: https://developers.cloudflare.com/r2/api/tokens/
- Bucket retention locks: https://developers.cloudflare.com/r2/buckets/bucket-locks/

No live environmental object upload, storage provisioning, merge, deployment, schedule change, historical deletion, or scientific promotion is claimed by this document.

Validation receipt: final full offline suite passed 655 tests with five expected Linux PowerShell skips, including 17 migration tests. Live cloud SDK, dedicated-bucket transfer, independent remote restore and production cutover remain untested.

# Jubilee Model Work Register
Updated: 2026-09-07. This is the canonical continuity and completion register for the existing Jubilee project. Update this file in place. Do not create another model or event database.

## Purpose and evidence limits
Deliver useful, location-specific early warning and confirmation for the Eastern Shore, with separate Point Clear and Daphne/May Day outlooks and intermediate Montrose, Fairhope/Fly Creek, Battles and Mullet Point cells. Improve accuracy with measured evidence, not data-volume or test-count claims.
This register reconciles accessible prior conversation evidence, owner instructions, saved main files, PR #4 and current scheduled-task configuration. The entire old conversation was NOT recovered verbatim. Therefore historical transcript completeness is UNVERIFIED. Preserve an explicit recovery gap; never claim every unsaved action was recovered.
Repository: bentsmith4/jubilee-camera-feed. Desktop production capture runtime remains C:\JubileeCams. A branch is not a deployed runtime.

## Binding owner decisions
- Hold new physical sensors. Retain prior designs as deferred; no purchase, deployment or renewed hardware work without a new owner instruction.
- No routine manual predawn/in-person spot-check requirement. Use unattended observations; accept incidental owner/trusted-local evidence when supplied.
- Keep four permanent roles: Jubilee Sensing & Alerting, Jubilee Dawn Brief, Jubilee Dawn Timing, Jubilee Model Research & Calibration. Do not revive paused predecessors or create duplicate model pipelines.
- Preserve current alert policy, including the >20% opportunity threshold and separately authorized material evidence/input-quality alerts. No new positive production predictor weight without validation.
- User-facing times are America/Chicago. An apparently UTC public-camera clock may be interpreted as UTC when the material offset supports that explanation; record the assumption, raw displayed time and normalized time. Do not relabel explicit timezone-aware CT captures.
- Useful pre-daybreak camera assessment requested; light/search signals can be assessed when visible. Biological absence requires actual usable illumination, not clock time alone. No repeated unchanged-darkness reports.
- Fairhope Pier sees neither north nor south beach. Use visible cars/people/lights, calm/chop, qualitative flag movement, birds and biology. No unseen-beach negative or uncalibrated numerical wind estimate.
- 437 shoreline camera sees waterline and nearby beach segments, cedar-stump references, and biology in sufficient light; no road/parking or vehicle count. It does not cover the full May Day-to-Fly Creek corridor.
- Point Clear private marina/Bay views do not establish a close beach/swash-zone negative. Preserve main and branch-specific geometry evidence.
- Same-site cameras share an independence group. Human searching is a soft precursor, never confirmation or identity recognition.
- Public camera media: observation-only unless retention rights explicitly permit otherwise. Preserve structured observations and provenance.
- Retain source evidence, immutable raw data, prior decisions and supersession history. No force push, no overwriting live camera commits. Use exact versions and checksum/ancestry guards.

## Verified baseline and unmerged work
Audit baseline main tree: 83cb6c249df8ee17bc4e33b4ec8a24fa1260c30e. This is a tree identifier, not a commit identifier; live publication continues.
PR #4 head inspected: 775734e6e38a9a078e23b7942039369641b7437e, branch upgrade/top5-gaps-round2-20260906, OPEN / NOT MERGED, 135 changed files at inspection.
PR-head check-runs API returned zero checks; combined commit status returned pending with no statuses. This is NOT proof that tests fail, and NOT proof that CI passed. Mergeability was unknown. Full changed-file/patch review and exact-head validation remain required.

Main: six successful three-frame captures and six matching vision results inspected from 2026-09-07 08:07–08:10 CT. Latest saved main regression report: 57 offline tests, zero failures/errors/skips; it does not validate PR #4 or current desktop end-to-end behavior.
Main consolidation report: 30,635 river rows and 7,650 water-quality observations; includes regional proxies/bacteria, not co-located Eastern Shore bottom oxygen.
Main event_history: 11 confirmed records. PR #4 event_history: 15 confirmed records; additions are three 1971 events and the 2017-08-26 Fairhope Yacht Club event. These classifications are saved research claims awaiting merge-stage evidence review, not independently re-researched in this handoff.
PR Main Pass manifest reports 211,308 normalized parameter rows across 29 profiles from April 19, 2016 (35,218 rows per each of six parameters). Do not call these 211,308 independent profiles/events. Manifest and CSV/archive existence verified; full raw-hash and row revalidation pending.
PR Weeks Bay manifest reports 53,323 rows (WKQA1 34,000; WKXA1 19,323). Regional proxy for open Eastern Shore bottom conditions; no production promotion.
PR includes NGOFS2 Point Clear, named-station and shoreline-grid model extraction, raw subsets, manifests and code. Maintain MODEL classification and provisional geometry/missing-cycle qualifications.
PR observation snapshot is from 2026-09-06 22:06 CT, outside its dawn window, and rejects both site groups for controls. It does not prove a working ongoing dawn ledger.
Verified clean matched training controls: zero in inspected evidence. Forecast skill: NOT ESTABLISHED.

## Work queue and closure tests
Statuses are mutually exclusive: VERIFIED_COMPLETE, IMPLEMENTED_PENDING_VALIDATION, READY_TO_EXECUTE, BLOCKED_EVIDENCE, DEFERRED_OWNER.
A workstream may contain both completed and unfinished subtasks; each row below refers to its precise deliverable.

| ID | Deliverable | Status | Evidence / remaining action | Closure test | Responsible role |
|---|---|---|---|---|---|
| J01 | Six-camera publication repair and core upgrade | VERIFIED_COMPLETE | main consolidation report, six-camera acceptance, current status/burst/vision; preserve two site groups | Reopen only on a fresh operational defect | Sensing |
| J02 | Public Fairhope/Grand Hotel interpretation contract | VERIFIED_COMPLETE | main public_camera_signal_contracts.json already contains owner corrections | Reopen only for changed view/clock/rights or inconsistent consumer | Sensing |
| J03 | PR #4 incorporation | IMPLEMENTED_PENDING_VALIDATION | OPEN at head above; code/data persisted; no exact-head CI proof | Review all 135 files, reconcile current base without replacing live outputs, run relevant/full gates, review provenance; safe merge, verify main and actual scheduled output; keep numerical weights zero | Research |
| J04 | Main Pass / Weeks Bay / NGOFS2 research data acceptance | IMPLEMENTED_PENDING_VALIDATION | manifests and datasets present on PR | Recalculate counts/hashes, units/depth/time/QC and availability semantics; distinguish physical source coverage; demonstrate reproducible incremental ingest | Research |
| J05 | Four added historical event records | IMPLEMENTED_PENDING_VALIDATION | 15 PR records vs 11 main | Review exact sources/date/location/independence and 1959 date ambiguity; preserve near-miss separately; merge once; verify no duplicates | Research |
| J06 | Unattended prospective observation-effort and scoped non-events | IMPLEMENTED_PENDING_VALIDATION | PR build_observation_effort_snapshot.py and matched_control_contract; inspected snapshot is old/outside target window | Fresh real dawn execution, immutable deduplicated record with capture identity, scoped geometry and illumination; counters for eligible/rejected/unknown; no blanket Point Clear negative | Sensing implementation with Research label acceptance |
| J07 | Historical human-control candidates | IMPLEMENTED_PENDING_VALIDATION | PR build_human_control_candidates.py and human_observation_recovery_20260907.json; derived candidate output absent in inspected head tree | Generate candidate output; verify 2024 May Day missing time/effort fields, 2012 near-miss and conflicting episode exclusions; admit no clean negative without required evidence | Research |
| J08 | Expand historical positives and recover scientific source tables | READY_TO_EXECUTE | Loesch 1946–1956 primary tables, May dated profiles, month-only 1959 and unresolved modern/social leads | Exact dated/geolocated source-backed rows, deduplicated with provenance; aggregate newspaper counts never become invented event rows | Research |
| J09 | Remaining priority physical archives and geometry | READY_TO_EXECUTE | NCEI 0188979/0224293, FOCAL/West End CP, Main Pass other releases, HFR, Ralston plume/SAR, DISL station-year archives/maintenance, ADEM depth profiles, Battles 2021 multibeam | Payload parsed and retained; source geometry/QC/units/time verified; discovery-only entries remain explicitly un-ingested | Research |
| J10 | Comparable event/non-event feature panel and held-out scoring | BLOCKED_EVIDENCE | Zero verified matched controls; candidate and contract code is not calibration | Build matched windows with available_at<=issue time; event/episode-blocked tests vs simple baselines; report false alerts/misses/lead time/calibration; promote only measured gains | Research |
| J11 | Dawn time and public clock reconciliation | READY_TO_EXECUTE | Current Timing task specifies dawn+25 minutes, operations_contract says +15, owner asked useful just-before-daybreak assessment | Reconcile pre-daybreak human/environment check and first-usable-light biology; retain daylight fallback and coverage; one consistent documented timing contract plus observed scheduled run | Dawn Timing / Dawn Brief |
| J12 | Stale documentation / scheduler-state reconciliation | READY_TO_EXECUTE | operations_contract still says task migrations NOT_APPLIED despite four active roles; README refers to two Montrose views | Reconcile documents against scheduler/desktop evidence; distinguish configuration verified from run/output validation; preserve history | Research / operations |
| J13 | Independent archive restore and runtime resilience | BLOCKED_EVIDENCE | Prior desktop archive/hash acceptance exists; later cloud independent restore not verified; desktop restart-setting change previously rejected | Authorized read-back hash/restore at current capture; inspect actual restart setting/capture recovery without bypassing access | Sensing |
| J14 | Full old-chat request and decision recovery | BLOCKED_EVIDENCE | Only partial transcript retrieval succeeded; screenshots prove later research continued | Reconcile any newly recovered final requests/progress with this register; record source and supersession; never claim exhaustive recovery until supported | Main discussion |
| J15 | New physical sensor package | DEFERRED_OWNER | Explicit owner hold supersedes prior design work | New explicit owner direction before restarting | Owner decision |

## Next execution sequence
1. J03–J07: recover, validate and safely incorporate already-written PR #4 work before expanding another parallel research branch. Finish the candidate-output step and prove unattended observation logging with fresh inputs.
2. J11–J12: reconcile operational timing and stale documents; preserve earlier coverage/alert instructions and test the actual result.
3. J08–J09: targeted event/control evidence and high-value archive ingestion, reusing existing parsed data and source hashes.
4. J10: evaluate forecast skill only after the data meet the control and leakage gates.
J13 requires suitable archive/runtime access; J14 remains an explicit completeness gap. J15 stays deferred.

## Reporting and change protocol
Before starting a run: read this register, source/event registries, current task configuration when relevant, latest main and any open relevant PR. Identify exact base/head and next work ID.
At each completed work boundary record: work ID, actual action, evidence paths and versions, new/updated row counts, validation outcome, main/branch/runtime destination, exact blocker and next action.
Do not count URLs as ingested data, candidate negatives as validated controls, code tests as predictive accuracy, or an open PR as production completion.
Use compare-and-swap content SHA on register/document writes. Re-read on conflict; preserve newer facts. Never replace latest camera-state files with research-branch copies.
At a chat handoff, update this register before relying on a conversation summary. Old chat titles and pins are user-managed; do not rename chats.
Keep scheduling and alert semantics unchanged unless executing an already-authorized, reconciled correction. No duplicate scheduled jobs.

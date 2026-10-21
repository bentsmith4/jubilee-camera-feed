# J08: June 1947 and August 1950 newspaper admission review

Reviewed October 21, 2026. Existing owner: Jubilee Model Research & Calibration; Jubilee Dot coordinates through MODEL_WORK_REGISTER.md. Review proposal, not merged or deployed.

## Decision

Three additional reported historical occurrences meet the existing dated/localized/source-backed admission convention. Propose 16 to 19 canonical research-only rows. This means three separately supported occurrence labels, not three statistically independent samples or demonstrated independent hydrodynamic causes. June 13 is weaker than the other two: locality is contextual, with no species or precise clock evidence. Two August locality observations remain uncounted because independence is unknown.

| Observation | Calendar interpretation and timing | Geography and source strength | Decision and deduplication |
|---|---|---|---|
| June 13, 1947 | June 16 Monday issue says first Jubilee early Friday morning; calendar resolves June 13 | Point Clear inferred from the surrounding statement that Saturday was the second within a week at Point Clear. Brief retrospective report, no species | Admit one qualified occurrence. Explicit first/second wording supports separation from June 14; adjacent dates alone would not. Do not assign a pier, exact onset, duration or species |
| June 14, 1947 | Saturday in June 16 issue; late afternoon, underway about dark and Saturday night | Point Clear, mayor Robin C. Herndon's pier and nearby beach/surf; named witnesses, flounder and crabs | Admit one occurrence, not one per witness. Same newspaper source group as June 13; no independent corroboration claimed |
| August 5–6, 1950 | August 7 Monday issue; Saturday about 7:30 p.m., cumulative catch by 3 a.m. Sunday, crab collecting Sunday daytime | Just north of Montrose / Winding Brook, reported quarter-mile between Montrose and Daphne; W. M. Bullock's account | Admit one episode with August 5 start-day label and August 6 continuation. The cumulative catch clock is not an end bound. Sunday is not a second event |
| August 6, 1950 Point Clear | Sunday, no clock supplied | Locality-only report explicitly lacking details; no event-specific species supplied | Retain observation only. Different town does not establish independent episode; do not append Point Clear to Montrose footprint |
| August 7, 1950 Daphne | Monday; flounder catch early in day, not an onset bound | Daphne locality, mainly crabs and a reported flounder catch | Retain observation only. Newspaper explicitly leaves new occurrence versus continuation unresolved; do not extend Montrose episode through August 7 as fact |

## Current-state and source review

Read main at `5b4a7da063a28aac061e0953c2ab1adf2f0e2676`, AGENTS.md, charter, shared register, original scan evidence, archival correspondence history, Loesch primary recovery and PR #88 admission precedent. The existing 16 rows have no June 1947 or August 1950 dates or overlapping candidate episodes. The September 17 row is preserved unchanged, as are all other original rows and their order. PR #91 remains open/draft with a 16-event timing inventory; the register records Dot consumption. Its old denominator is a historical snapshot, not a current 19-row result. No competing June/August admission PR was found among open PRs.

Used the already retained Library PDFs, version 0, without another archive request. Visually inspected both full pages (mastheads, Monday publication dates and Final Edition) and enlarged complete articles. Both match the retained observation chronology. Calendar checked independently in regression tests: June 13 Friday, June 14 Saturday, June 16 Monday; August 5 Saturday, August 6 Sunday, August 7 Monday. Local clock standard is unknown; the existing `event_date_ct` schema key carries a local calendar label, not an asserted historical UTC offset.

Loesch's 1960 excerpts derive from these newspaper reports. Librarian supply authenticates the retrieval lineage but is not a second event witness. Named witnesses within one article do not create independent sources. June's two events share one source group. August's three locality reports share one article and cannot support three independent episodes. No correspondence, scan, original source hash or prior recovery result is overwritten.

## Exact source identities and limits

| Issue | Retained Library item | Reviewed PDF bytes / SHA-256 | Embedded 2400-pixel-wide scan JPEG SHA-256 |
|---|---|---|---|
| 1947-06-16 | libfile_ebc3326ec2248191b98665d29363b3dd | 1,448,253 / `a1a395554d05403c3d03ac68962a887bbc240b05ca40189665bf1af5fa8935f5` | `261db50b836da0f00e68dd224b200cac6825dac2dcdb46ce96bef99da580d65e` (2400 x 3056) |
| 1950-08-07 | libfile_ebf01f0a76e88191a03515c1307b41ef | 1,212,162 / `3950263b48a368d3caa077f2f50d495384cccbf252673da7abc985e36a08597e` | `c6d553b34e1413fa5c789f4321f10e5fd56078d0705593f1213c8b80189507b1` (2400 x 3127) |

These Library PDF containers differ from the originally received attachment hashes in the immutable October 3 record (`463c8cef...` and `340309e1...`). Those original hashes remain source-provenance fields; this review does not claim to have rehashed the original attachments or proved byte equivalence. The materialized source pages were directly legible and visually reviewed. Cause of container difference is unverified. Front page and article placement are visible; exact column labels remain librarian-supplied.

## Model utility and restrictions

These are usable qualified local-calendar and locality positives for future historical evaluation design. June 14 and August 5–6 add afternoon/evening and cross-midnight coverage; June 13 supplies early-morning wording only. None supplies verified exact onset/end or measured event-site oxygen, salinity, current or meteorology. No modern camera ROI is bound, and no environmental join, calibrated training set, negative control or demonstrated predictive improvement is created. Historical editorial confidence scores describe evidence, not forecast probabilities.

All three rows are research-only, production weight zero, calibration ineligible and prohibited from whole-day-negative inference. Potential future evaluation must retain source clustering and possible shared forcing across adjacent dates; do not treat June's two rows as independent training/test samples merely because the article calls them distinct occurrences. Loesch's unresolved 35/37 aggregate discrepancy remains untouched. September 17 admission and its uncertain Battles Wharf/photo links are not reopened.

## Validation and coordination

The proposed history retains the exact prior 16-row document when the three new IDs are removed: SHA-256 `875c5d198535ce9338ca1b58e205c1de126b6d0c5e209589b02a16f39836112c`. Existing tests also reconstruct the original 15-row document after removing the four explicitly reviewed J08 additions. Regression guards check weekday derivation, one cross-midnight August episode, excluded uncertain observations, shared June source lineage, unchanged source bytes, and research-only/zero-weight flags. Earlier recovery counts remain historical; their zero admissions are not rewritten.

Handoff stays in J08 and the single shared register. Draft PR/review readiness does not imply native Dot acknowledgment, independent reviewer approval, merge or deployment. Production forecasting probabilities, weights, alert thresholds, camera coverage, schedules and the 9 p.m. Central notification restriction remain unchanged.

Sources: [retained scan evidence](loesch_newspaper_scan_evidence_20261003.json), [archival history](LOESCH_1960_ARCHIVAL_FOLLOWUP_20261003.md), [primary Loesch review](LOESCH_1960_PRIMARY_RECOVERY_20261002.md), [prior admission convention](J08_DAPHNE_1950_ADMISSION_20261013.md), [existing timing PR #91](https://github.com/bentsmith4/jubilee-camera-feed/pull/91).

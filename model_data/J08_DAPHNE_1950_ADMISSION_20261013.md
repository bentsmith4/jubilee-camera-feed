# J08: September 17, 1950 Daphne Jubilee admission review

Reviewed October 13, 2026. Owner: existing Jubilee Model Research & Calibration; Jubilee Dot coordinates through the shared register. Proposed historical-record addition; merge/approval pending.

## Finding
The original newspaper independently supports one dated Daphne historical Jubilee. The photograph is compatible but cannot be assigned to that occurrence on present evidence. Admission does not depend on proving the photo link.

| Evidence | Date meaning | Supported finding | Limit |
|---|---|---|---|
| The Mobile Press, September 18, 1950, p. 6-B, columns 1-2 | Publication date | Detailed Sunday afternoon/night Jubilee in Daphne vicinity | One newspaper source group, not independent observations per witness |
| Sunday and 5:30 p.m.-around midnight in that article | Calendar-derived September 17 event date; approximate local clock wording | Afternoon/evening event, not a dawn-only event | Historical time standard unknown; no UTC conversion |
| Daniel's October 5 McCall correspondence | Photograph metadata dated 9-17-1950 | Thigpen 747, S-249-16, reading-room 35H-B3-12-3; Daphne metadata | Does not identify date as exposure/event/publication/catalog attribution |
| University web photograph | Web derivative; caption supplies 1950 only | Two people wading with collection implements and a light, compatible with harvesting | No independently readable date/location; no match to named newspaper witnesses established |

## Primary-source verification
- Recovered the original September PDF from Gmail message 1a1039dd3a37f347, visually inspected the full page/date line and enlarged article. Byte size 1,387,225; SHA-256 1087181cb1ea78aa7ccc33e49637f47d17c4d4fd9b5b3eaf69709a45bc978e6c matches the October 3 evidence record. Existing durable source: libfile_b4f200a92c94819192c074218b2aaae6. No replacement source copy needed.
- Printed page: The Mobile Press, Monday September 18, 1950, 6-B. Headline: Year's Biggest Jubilee Brings Flounders, Crabs To Daphne. Calendar independently checked: September 17 was Sunday.
- The story reports hundreds harvesting flounder and hard/soft-shell crabs, with eels also reported. Named witnesses include Daphne residents and a resident approximately one mile south of Daphne. Those are reported locations, not a continuous shoreline boundary.
- Keep the seven-hour description alongside approximate 5:30 p.m.-midnight bounds; do not manufacture precise duration.
- Re-read Daniel's original email 1a10cab09377ace5. Later bounded McCall mail search returned only that reply and the October 5 courtesy response, with no additional original binder or date-semantics evidence.
- Downloaded and visually inspected the linked university derivative. Its visible harvesting scene adds no independently resolvable day or location. University article labels it 1950; its filename is not an event-date source. Original negative/print and binder remain unrecovered.

## Admission and deduplication
Add only 1950-09-17-daphne to event_history.json: 15 to 16 records on this proposal. Preserve all original 15 records byte-for-byte and their order. Historical evidence confidence 0.97 is an editorial score, consistent with the existing calendar-inferred newspaper record convention, not calibrated event likelihood; narrative qualifications control interpretation. No existing confidence value changes.
Retain one source-independence group. The photo is a related unresolved lead, not a second positive or independent confirmation. Battles Wharf's smaller crab-only report around 10:30 p.m. remains a separate observation in the existing scan evidence; baywide episode independence is unknown, so do not add another event or extend Daphne geography.
This is admission of an already recovered observation, not a newly discovered scan. PR #56 recovered newspaper evidence and PR #64 recorded McCall provenance. Their historical zero-admission statements remain accurate for those dates. Loesch's 35/37 discrepancy remains unresolved.

## What would establish the photograph link
Obtain the complete S-249-16 binder entry with neighboring sequence/date context, original print verso or negative sleeve, and explicit custodian explanation of the date field. Seek a contemporaneous caption, photographer log or assignment entry tying this exact image to the September 17 Daphne occurrence. Shared date and town alone are insufficient.
These materials were already requested October 3. No repeated email or new paid request was sent. Any renewed institutional outreach needs Ben's specific permission under AGENTS.md. This is separate from the already assigned Mobile Municipal Archives RG34 onsite investigation; no researcher assignment or duplicated archive search is created.

## Model and workflow limits
Research-only event, zero production weight. No forecast probabilities, existing production weights, alert thresholds, notification policies, schedules, camera coverage or nine-PM gate changed. No automated retraining, environmental joins or lunar rerun performed. Prior analyses tied to the old 15-record hash remain historical outputs and are not re-described as analyses of 16 records. Predictive improvement is not demonstrated.
Proposed changes are limited to event_history.json, this review, and the existing MODEL_WORK_REGISTER.md J08 entry. Dot consumption and approval are not implied by a branch/PR.

## Sources
- [Original newspaper correspondence and PDF](https://mail.google.com/mail/u/?authuser=bentsmith4%40gmail.com#all/1a1039dd3a37f347)
- [McCall October 5 identification](https://mail.google.com/mail/u/?authuser=bentsmith4%40gmail.com#all/1a10cab09377ace5)
- [Existing scan evidence](loesch_newspaper_scan_evidence_20261003.json)
- [Existing archival history](LOESCH_1960_ARCHIVAL_FOLLOWUP_20261003.md)
- [PR 64 provenance](https://github.com/bentsmith4/jubilee-camera-feed/pull/64)
- [University photograph](https://www.southalabama.edu/departments/publicrelations/pressreleases/images/2021/062821jubilee750a.jpg)
- [University article and year-only caption](https://www.southalabama.edu/departments/publicrelations/pressreleases/062821thigpen.html)

Validation: original PDF hash matches; calendar day checked; original page and enlarged article reviewed; JSON parses; original 15 event objects and file content preserved; exactly one unique new event ID; changes restricted to three historical/review files. Merge and live deployment not performed.

## Integration review — October 13, 2026

The preceding three-file scope describes the original proposal. The existing PR #88 now also carries regression guards for the single admitted row and the immutable earlier recovery audits. The current 16-row history is distinct from the September 29 / October 2 / October 3 historical results: their 15-row counts, zero promotions, empty matches, original history hash and unresolved Loesch 35/37 arithmetic are retained. Removing only `1950-09-17-daphne` from a copy and serializing with `json.dumps(indent=2, ensure_ascii=False)` plus a final newline reproduces original SHA-256 `dab32ef7e5a0bf4edefb8e998a759ef30aa551feafe61da4d78bbb266cf4dca2`.

An independent source check recovered the exact original attachment from the already-cited Gmail message and visually verified the article. **PDF identity clarification:** `source_sha256` refers to the original Gmail PDF, 1,387,225 bytes, SHA-256 `1087181cb1ea78aa7ccc33e49637f47d17c4d4fd9b5b3eaf69709a45bc978e6c`. The cited Library item `libfile_b4f200a92c94819192c074218b2aaae6`, version 0, materializes as a different PDF container: 1,412,381 bytes, SHA-256 `c5a48c8ee6ee2c9fbd0e1656edfc746ddca0454c6f1795432a79aaf62993b0ec`. Both embed the byte-identical 2400-by-3020 scan JPEG, SHA-256 `99c96755518fb6289bb3b1988571c52fa2c2a67a1bf7f4f6f112c23d04f3643c`, and produce byte-identical page renders with the same rendering settings. They are content-equivalent, not byte-identical PDFs; the reason for the container difference is unverified. No retained source hash was replaced.

The source-admission review supports one Daphne occurrence, while the photograph remains unlinked and Battles Wharf remains a separate observation with unknown independence. This clears source review only; exact-head automated checks and merge verification remain separate gates. Research/archive ownership is unchanged. No new archive search, outreach, paid model call, production change or predictive-skill claim is made.

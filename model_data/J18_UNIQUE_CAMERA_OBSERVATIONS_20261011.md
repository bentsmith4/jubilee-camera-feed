# PR #76: what the 17 unique camera observations actually show

Research review: October 11, 2026. **Production action: NO_CHANGE.** No paid model calls, no PointClearPC experiments, no scoring correction repeated, no camera suppression proposal.

## Finding

The corrected count is reproducible, but it is not a count of Jubilee detections. Of the **17 unique camera observations**, **16 are positive only because `people_present=clear`**. The remaining observation contains both `fish_surface_activity=isolated` and `fish_jump_activity=isolated`; those two fields describe one camera observation, not two events.

The mutually exclusive interpretation is:

| Interpretation | Cases | Implication |
|---|---:|---|
| Ordinary human presence supported by the stored summaries | 15 | Sitting, reclining, walking, dock/boat activity; little demonstrated predictive information |
| Human label inadequately explained by its summaries | 1 | September 26 E3; classification validation needed, no supported Jubilee inference |
| Isolated biological/surface-disturbance candidate | 1 | September 29 Montrose bird; worth validating, but neither abnormal physiology nor precursor significance established |
| Established Jubilee or independently validated precursor | 0 | Sensitivity, specificity, missed-event rate and lead time remain not estimable |

None of the 17 has a scored positive for gulping, shrimp concentration, swimming/climbing crabs, displaced bottom fauna, shoreline accumulation, lethargy, bird feeding, flashlight activity, clustered searching, seafood collection, repeated surface activity, or moderate/strong overall or temporal Jubilee signal. Ordinary calm water, ripples, chop, reflections and boat wake are environmental context, not extra biological detections. This review does not recode any source label.

## Sources and reproducibility

- Replay source: original PR head `519d5bfdc5abe64fb5eb1fa7da009531c9467e64`. Enumerate `git log <head> --format=%H -- vision.json`; read each committed state. All **931** states are readable, September 4 11:06:02 through October 8 10:06:05 CDT. Reuse the unchanged scorer pinned at research head `c73cf645e43c8e30fc34574f9d8c957098a16c3a`; do not rerun or modify the old scoring correction.
- Outcome/context evidence: main commit `9f32b0494c70b63778c4ffca2efa975c7e8137a0`, including event history, owner reports, observation records, private-camera geometry contracts, J10 controls and public-camera log. Pinning separates the replay archive from later outcome review.
- Companion `j18_unique_camera_observations_20261011.json` retains every case's exact vision commit/blob/SHA256, positive fields, summaries, quality/confounder fields, all three recorded shot times and timing semantics, peer states and shot times, status/burst provenance, original canonical-image blob/SHA256/bytes, linked observation records and outcome joins. It also retains the four non-unique positives and nearby biological-case captures.
- All **17/17** case status and burst files match the vision capture identity and report a successful subject-camera capture. All **17/17** retained canonical JPG byte counts match the reported final shot. The corresponding immutable observation records independently match both the vision SHA256 and final-image SHA256 for **17/17** cases. A byte-count match alone is not a hash verification; both checks are retained.
- Original final images were inspected: all 17 in contact sheets, plus full-size September 29 bird and September 26 E3. September 28 bubbles were reviewed full-size as ancillary context. This is a direct visual review of existing images, not a new paid image-model analysis. No media is added to GitHub. The root history retains a canonical final image, **not the complete three-frame burst**; frame-1/2 behavior and temporal persistence remain the prior analysis's claims. No identity recognition or person tracking was performed.

Run from the repository root using a full clone with the pinned commits:

```bash
PYTHONDONTWRITEBYTECODE=1 python model_data/investigate_camera_unique_observations.py --output /tmp/pr76-cases.json
cmp /tmp/pr76-cases.json model_data/j18_unique_camera_observations_20261011.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_camera_marginal_value.py
```

The extractor fails closed on unreadable sources, changed scorer bytes, count disagreement, capture-identity failure or case image/observation-hash mismatch. It performs no network or model calls. Manual ecological interpretation is documented here rather than silently embedded in a scoring rule.

## Case inventory

Times below are **CDT (UTC−05:00)**. Cycle time is the scheduler/capture identity; subject-camera shot times are more precise evidence times. `G/M` means stored good visibility/moderate detectability; `G/H` means good/high. These are model quality labels, not independently measured biological sensitivity. `A` means actual screenshot timing; `N` means nominal intervals from a single stream. Full fractional seconds and full commit SHAs are in the JSON. Commit prefixes locate each original `vision.json` and `<camera_id>.jpg`.

| # | Cycle date/time | Camera | Subject burst times | Quality/timing | Positive category and supporting description | Source commit |
|---:|---|---|---|---|---|---|
| 1 | Sep 7 16:06:02 | Montrose boat | 16:06:07–16:06:27 | G/M A | People: one seated, no searching/collecting | `e4f67c0f1` |
| 2 | Sep 10 14:06:00 | Montrose boat | 14:06:05–14:06:25 | G/M A | People: two stationary/lounging | `d480ea380` |
| 3 | Sep 11 09:06:03 | Montrose boat | 09:06:08–09:06:28 | G/M A | People: standing person in frame 2, no search equipment | `ff4885969` |
| 4 | Sep 11 19:06:01 | Montrose boat | 19:06:06–19:06:26 | G/H A | People: reclining in hammock; moderate chop | `43a70ae67` |
| 5 | Sep 12 09:06:00 | Point Clear E3 | 09:08:18–09:08:38 | G/M N | People: dock walking/repositioning, no collection | `15b9fcd88` |
| 6 | Sep 12 17:06:04 | Montrose boat | 17:06:09–17:06:29 | G/M A | People: hammock and partially visible second person | `799376f1c` |
| 7 | Sep 12 18:06:38 | Montrose boat | 18:06:42–18:07:03 | G/M A | People: walking/standing on walkway | `906e24e98` |
| 8 | Sep 12 19:06:24 | Montrose boat | 19:06:29–19:06:49 | G/H A | People: reclining; chop and possible artificial-light effects | `ad7644f7d` |
| 9 | Sep 12 20:06:05 | Montrose boat | 20:06:10–20:06:30 | G/M A | People: resting; **night scene, strong artificial light/reflection confounding** | `b44d0629c` |
| 10 | Sep 13 18:06:00 | Point Clear E3 | 18:08:19–18:08:39 | G/M N | People: moving between boat and dock, no collecting/searching | `df2db94a7` |
| 11 | Sep 18 14:06:03 | Point Clear E2 back deck | 14:06:47–14:07:07 | G/H N | People: stationary on deck, quiet marina | `e6b99d025` |
| 12 | Sep 18 19:06:02 | Montrose boat | 19:06:10–19:06:30 | G/H A | People: seated; chop and possible artificial-light effects | `5e775a3b1` |
| 13 | Sep 26 13:06:01 | Point Clear E2 bay mouth | 13:07:11–13:07:32 | G/M A | People: boat occupants; change explained by **boat wake** | `e0c9dbaca` |
| 14 | Sep 26 14:06:00 | Point Clear E3 | 14:08:21–14:08:41 | G/M N | **Ambiguous:** clear people label, but all summaries describe quiet marina only | `ef38a997b` |
| 15 | Sep 28 16:06:01 | Montrose boat | 16:06:06–16:06:26 | G/M A | People: two under shelter, slight repositioning | `70715f2d6` |
| 16 | Sep 29 06:24:25 | Montrose bird | 06:27:46–06:28:06 | G/H A | **Biological candidate:** isolated fish/jump labels; distant disturbance in frame 3 only | `df38fa32b` |
| 17 | Oct 2 18:06:00 | Montrose bird | 18:08:46–18:09:06 | G/H A | People: seated/walking/at edge, no increasing disturbance | `ec1841e35` |

Counts reconcile to Montrose boat **10**, bird **2**, shoreline **0**; E2 back deck **1**, E2 bay mouth **1**, E3 **3**. The 17 cases cover **10 dates**, not 17 statistically independent event episodes. Five September 12 human observations include repeated afternoon/evening use of one pier; no attempt is made to count unique people or independent human responses.

## Cases meriting validation

### 1. September 29 isolated disturbance — highest priority within the 17

At actual shot 3, **06:28:06.291140 CDT**, the canonical bird-view image contains a small distant surface disturbance. Review does not establish animal identity, abnormal physiology, density or a fish jump independently. Stored summaries say frames 1 and 2 contain no visible animals; frame 3 alone contains the disturbance. `temporal_persistence=one_frame`, `repeated_surface_activity=none_visible`, gulping/accumulation/displacement fields are negative, and overall/temporal Jubilee labels are `weak_possible`. Cross-camera synthesis says limited temporal confirmation and no spatial confirmation.

The same-site peers are assessed negative under the existing scorer, but they were sampled earlier: boat **06:24:31–06:24:51**, shoreline **06:26:37–06:26:58**, bird **06:27:46–06:28:06**. This is same-cycle uniqueness, not proof that three cameras saw the same transient at the same instant. The next four morning cycles, **06:45:09, 07:05:29, 07:25:41 and 07:45:37**, classify the bird view negative with good visibility and moderate/high detectability. Earlier low-light cycles remain UNKNOWN. Observational gaps are not interpolated.

The exact cycle's immutable observation record (`4555fda4609cc82f5b3e4cd5.json`) labels the **shoreline-contact pixels** a candidate visible-scope control while retaining the bird-view `weak_possible` label. These can coexist: the bird view looks roughly 150+ feet offshore, and the shoreline record does not negate that disturbance or prove Montrose had no event. Point Clear E3 failed that cycle and E2 deck was poor/low; those gaps cannot serve as regional negatives.

Later public observations are also scoped: Grand Hotel **06:49:44–06:50:08** failed freshness/progression assessment and remains UNKNOWN; Fairhope **06:50:52–06:51:08** was probably fresh and reported ordinary pedestrians with no repeated fish activity/searching in its visible area. Fairhope beaches and Fly Creek were not visible. Neither establishes the outcome at Montrose.

**Decision:** retain as an unresolved isolated-disturbance challenge example, not a positive Jubilee or precursor. If the existing burst originals become available through the already assigned archive work, validate animal identity and progression against frames 1–3 and neighboring bursts. No additional capture, paid analysis or separate crop experiment is initiated here. A single ordinary jump remains a plausible explanation; hypoxia-driven behavior is not established.

### 2. September 26 E3 human label — classification validation

`people_present=clear` is the only scored positive. All three frame summaries and temporal summary discuss quiet marina water/docked boats and do not explain human presence. The retained final image does not clearly resolve a foreground person; distant/occluded activity or earlier frames cannot be ruled out. Human sensor score is 0.0, searching/collecting/flashlights are negative, and overall/temporal Jubilee signals are none. A zero human score is contextual evidence, not proof the people label is false.

**Decision:** mark as inadequately supported pending original-burst validation. Do not delete or correct the original label, and do not count it as an ecological signal.

### Ancillary September 28 bubbles — outside the 17, but relevant to selection bias

The full 21-positive set contains a second surface-activity candidate at **05:39:11 CDT**, actual bird shots **05:41:55–05:42:15**, source `441dea80cdacfc50dc26f8f7b5f0d47b7172f147`. `repeated_surface_activity=clear` is positive, but both Montrose peers are UNKNOWN, so it cannot be called unique. The preceding **05:19:27** cycle describes unexplained persistent disturbance; **05:59:14** describes persistent bright spots without identifiable animals; **06:19:12** and subsequent daylight cycles are assessed negative. The final night image shows bright localized spots near the railing and broader bright surface features; it does not establish bubbles or animal identity independently. Reflection/illumination remains a competing explanation.

This is a worthwhile **artifact-versus-biology** validation case, not a recovered event. Excluding it because uniqueness is unassessable would discard potentially interesting observations precisely when peers are least observable. The three other non-unique positives are human presence: shared Montrose boat/shoreline on September 17 and E2 deck on September 10 with an UNKNOWN E3 peer. They supply no confirmed biological precursor.

## Confirmed-event and non-event cross-reference

- Current pinned event history contains exactly two confirmed **2026** events: **August 29 and August 30**. No case date matches either. **Zero** replay snapshots fall on either August date. No September/October case has independent confirmed-event linkage in the inspected event file. This absence is a missing label, not proof of no Jubilee.
- The September 12 owner report explicitly says no event on the Eastern Shore. It overlaps cases **5–9** (five human-only observations) and supports treating those as background presence rather than positive event detections. Its observation hours, effort and continuous coverage are unspecified; it is not a Tier-A matched control or five independent negatives, and it cannot validate other dates.
- September 9's marina report remains UNKNOWN and overlaps none of the 17. Do not extrapolate that record or the September 12 non-event to adjacent dates.
- Sixteen human cases are outside the canonical dawn target window in their exact observation records. The September 26, September 28 and October 2 dawn-control audits do not cover their afternoon/evening cases. The September 29 bird case is inside the window but has only the shoreline-scoped non-detection described above. Existing J10 controls have no completed matched positive-camera comparison; this review adds none.
- Existing private geometry contracts limit Montrose pier views to supporting shallow/offshore water and Point Clear views to marina-water/structures. Point Clear quietness does not establish absence on nearby beaches. Same-site views are not independent confirmations.

## What this establishes — and what it cannot establish

**Established:** the archive recovers view-specific human activity and at least one isolated disturbance that other same-cycle views did not report. The existing broad positive vocabulary includes routine human presence, so unique-count totals overstate their apparent ecological importance if described as Jubilee signals. Montrose boat's 10 unique observations are all human presence; its numerical lead does not demonstrate superior Jubilee sensitivity. Zero unique shoreline observations does not prove shoreline redundancy.

**Not established:** any new confirmed event, precursor, causal mechanism, forecast improvement, useful lead time, sensitivity, specificity, false-alert rate, missed-event rate, or safe camera/cadence reduction. Counts of descriptions cannot replace event-linked camera evidence. The missing August positive-event camera archive is the central retrospective detection gap. Whether the separate existing PointClearPC archive effort can recover those frames remains outside this investigation and is not asserted either way.

Preserve all six cameras, current capture/analysis schedules, production weights, probabilities, thresholds, alert policies and UNKNOWN handling. Keep PR #76 draft/research-only. No merge or deployment is performed.

## Validation receipt

- Extracted all 931 pinned vision states with zero failed reads; reconciled 21 positives and 17 unique observations using the unchanged scorer.
- Verified 17 case capture identities, final-image byte counts, immutable vision hashes and image hashes; all passed. Exact-source manifests and evidence times are retained in the companion JSON.
- Reproduced the generated JSON a second time byte-for-byte; checked the 16 human/one isolated-biological field partition and five September 12 overlaps independently.
- Ran the existing 15 focused camera-marginal-value regression tests; all passed. No production files, original audit/scorer, event labels or crop experiments changed.

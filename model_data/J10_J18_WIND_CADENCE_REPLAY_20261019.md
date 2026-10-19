# J10/J18 wind-dependent cadence: retrospective sensitivity, October 19, 2026

**Recommendation: retain production cadence.** Ben authorized the offline plan on October 19. This delivers a bounded retrospective replay, not an operationally validated wind rule, deployment, or actual invoice-saving claim. Existing Research & Calibration owns J10/J18; Jubilee Dot remains coordinator. Native Dot consumption of this new report is pending.

## Coordination and source identity

Checked AGENTS.md, DOT_PILOT_CHARTER.md, MODEL_WORK_REGISTER.md, open wind PR search, and canonical Ben action ledger version 45 before changes. No competing wind-cadence implementation was identified. Reused the October 15 J18 cost receipt, existing ASOS normalization/QC and immutable effort records. Related J08 timing and J18 economics have prior native Dot consumption receipts; this does not imply consumption of this new report.

Repository input commit: `7740bd80ca9a7864d440ffa1da24021ff73283e3`. Input manifest SHA-256: `19889a5ed8d265320567bae720ccce40ca5ba27ae84830ab1d69384949bcdb19`.

- 464 archived public AWC responses contain 1,402 unique decoded reports.
- 1,219 immutable effort records identify 1,219 distinct capture times.
- 638 capture times overlap the weather archive: September 27, 16:06 CDT through October 19, 10:06 CDT. This is an observed-record denominator, not an expected-cycle or validated six-camera-completion denominator.
- Only 335/638 cycles have continuously usable KBFM/KMOB provider-receipt proxy state over the preceding hour; 291 over two hours. Missing, stale, variable, conflicting and failed-QC evidence is ineligible, not low wind or negative biology.
- KCQF has only 58 one-hour and 55 two-hour usable profiles in this overlap. Its separate sensitivity must not be silently substituted for the longer KBFM/KMOB record.

## Method and strict limitation

The 120 scenarios cross five thresholds/directions, one/two-hour persistence, KBFM+KMOB agreement versus KCQF alone, dawn protection on/off, and 25/50/75% reductions. North is [315,360) plus [0,45); northeast [45,90); other [90,315). All directions are meteorological FROM. Speeds are sustained knots, not gusts.

Existing `ingest_asos_weather.normalize` supplies report QC. Both sides of every provider-receipt and 90-minute expiry boundary are inspected across the persistence window; a brief reversal, disagreement, expiry or unknown interrupts qualification. This is persistence of sampled, held-valid regional observations, not proof of uninterrupted shoreline wind. Newer invalid data cannot be backfilled from older good reports. Reports after a candidate decision time are excluded. Tied conflicting reports are rejected.

**Provider receipt is not Jubilee local first availability.** Raw archives do not by themselves establish historical local retrieval/publication timing. This replay assumes availability at provider receipt solely for retrospective sensitivity. Operational as-of eligibility remains UNKNOWN until exact historical normalized/manifest/commit evidence closes that gap. No runtime decision may consume these results as a validated rule.

Skip selection accumulates the requested fraction within consecutive eligible runs and resets on every protected/ineligible cycle. This deterministic conservative phase is not a randomized trial or all-phase bound. Protected dawn means the existing target-window flag must explicitly be false; missing flags do not authorize skipping. No current skipped-frame signal is used to veto its own skip, avoiding hindsight leakage. A future prior-observation safety veto needs separate testing.

## Results: primary two-airport sensitivity

All rows below preserve the full dawn window. Dollar estimates first use the October 15 post-change camera average $0.01182465/cycle, with synthesis held unchanged. Applying that average to earlier dates is a standardized sensitivity, not historical billing. The modeled total baseline is 638 x $0.01258312 = $8.02803056 over the observed overlap.

| Wind/persistence | Reduction | Eligible / skipped cycles | Conditional avoided camera cost | Usable camera samples removed |
|---|---:|---:|---:|---:|
| >=10 kt, any direction, 1 hour | 25% | 31 / 5 | $0.0591 | 18 |
| >=10 kt, any direction, 1 hour | 50% | 31 / 13 | $0.1537 | 54 |
| >=10 kt, any direction, 1 hour | 75% | 31 / 21 | $0.2483 | 91 |
| >=15 kt, north, 1 hour | 25% | 10 / 0 | $0 | 0 |
| >=15 kt, north, 1 hour | 50% | 10 / 4 | $0.0473 | 14 |
| >=15 kt, north, 1 hour | 75% | 10 / 5 | $0.0591 | 15 |
| >=15 kt, north, 2 hours | 50% | 5 / 1 | $0.0118 | 1 |
| >=20 kt, north, 1 hour | 50% | 1 / 0 | $0 | 0 |
| >=15 kt, northeast, 1 hour | 50% | 0 / 0 | $0 | 0 |
| >=15 kt, other directions, 1 hour | 50% | 0 / 0 | $0 | 0 |

Zero skipped cycles at the 25% north rule reflects short interrupted eligible runs and the stated phase; it does not mean no strong north wind occurred. Zero eligible northeast/other cycles is specific to this short archive, two-airport agreement, persistence and missingness rules, not a climatological conclusion.

The 50% one-hour north scenario removes one upstream `unclear` signal at Point Clear E2 bay mouth on October 17, 00:06 CDT. People were unknown and no flashlights visible. This is **not a confirmed biological precursor or Jubilee**, but also not a proven dispensable negative. The 10-knot scenario removes two non-quiet upstream rows. Raw output retains every skipped capture time for review.

Without dawn protection, the 10-knot/one-hour/50% scenario skips 22 cycles and removes five scoped candidate cells. With protection it skips 13 and removes zero. These cells are not independent validated negative days.

The maximum interval between retained capture records grows from 121.28 minutes to 241.44 minutes for both primary 50% scenarios. This is the largest capture-record gap over the whole overlap, not biological detection delay, usable-visibility coverage or a measured event miss. Existing nighttime gaps mean simply halving cadence can create approximately four-hour intervals.

KCQF-only, dawn-protected 10-knot/one-hour/50% sensitivity qualifies 10 and skips four cycles; all >=15-knot directional candidates qualify zero. Short availability prevents an equal-period station comparison.

## Independent PointClearPC usage readback

Read existing `C:\JubileeCams\frames\api_usage.jsonl` without modifying it, running inference, collecting images or touching the service. 7,784 rows; read-byte SHA-256 `9636cf0c2b3fc87dc62657156d41e31b61afb3a53cc329e58f28c84954474e04`. No private request/account identifiers or raw usage records were exported. Selected capture IDs and exact status/burst input hashes were matched to repository effort records.

| Dawn-protected, one-hour, 50% scenario | Selected cycles | Matching camera attempts | Exact status/burst hash matches | Cycles with one completed output per all six stages | Conditional recorded-token cost |
|---|---:|---:|---:|---:|---:|
| >=10 kt, any direction | 13 | 75 | 75 | 11 | $0.15146188 |
| >=15 kt, north | 4 | 22 | 22 | 3 | $0.04399592 |

All selected attempts were priceable using the inherited J18 model/rate assumption and explicit cache-write partition. Formula: `((input-cached-writes)*0.20 + cached*0.02 + writes*0.25 + output*1.20)/1e6`. No reasoning/image double counting. These observed-token sensitivities corroborate the small scale of the average-cycle estimates; they do not establish causally avoidable spend. Missing camera completions receive no complete-cycle credit. Full 18-image readback was not repeated; status/burst hash matching is narrower than image/effectiveness acceptance. Actual invoice reconciliation, SDK retries and altered cache behavior remain unresolved.

## Detection and scientific gates

- No canonical positive event overlaps this September 27 onward replay; August 29–30 have no retained positive camera replay. Event misses, sensitivity, false-alert rate and lead-time effects are not estimable.
- Usable effort uses existing capture/integrity and good/fair visibility plus moderate/high detectability criteria. Upstream classifications are not independent pixel review. Same-site cameras are correlated; no six-independent-site claim.
- Skipped intervals stay UNOBSERVED. Zero lost scoped candidates with dawn protection does not prove zero lost scientific value outside dawn. Wind-selective observation introduces sampling bias.
- Alligator fields are absent from these effort records; safety equivalence is UNKNOWN, not zero risk.
- Loesch Table II still has 12 N, 5 NE and 3 NW of 33 eastern-shore event-time Bates Field directions. It is positive-only direction evidence, not speed-conditioned event probability or a calibrated cutoff. No historical count discrepancy was resolved here.

## Existing-owner next action and stop conditions

1. Retain ordinary six-camera production collection, compact-output deployment and rollback. No new background job, paid call or collection has been created.
2. At the existing J10/J18 review, consume this report and receipt once. Recover local first-availability from existing historical manifests/commits before claiming operational replay; do not repeat paid image analysis or the completed PR78 acceptance.
3. Reuse ordinary future observations and existing original-burst recovery ownership for positive-event coverage and alligator/biological effectiveness. Test all skip phases, prior-observation safety vetoes and maximum-gap caps before any pilot. Revisit only when new evidence can change the decision; do not create another scheduler.
4. A reversible pilot remains NOT AUTHORIZED by this research result. Given four cents of recorded-token cost in the principal north scenario and no event-safety bound, there is no current economic or scientific case to deploy one. Merge, production cadence, weights, probabilities, alerts and 9 p.m. Central policy remain unchanged.

## Reproduction and verification

Run from the pinned input checkout: `python model_data/replay_wind_cadence.py --out /tmp/new-wind-replay.json`. Output creation is exclusive. Companion: `j10_j18_wind_replay_20261019.json`. Seven boundary tests cover sector edges, future receipt, freshness expiry, invalid newer data, conflicting reports, short direction shifts, missing-station/gap rejection and skip-phase reset. No runtime imports or producer writes occur. Deployment acceptance and empirical validation are deliberately not claimed.

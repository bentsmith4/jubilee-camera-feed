# Jubilee Consolidation Sprint — 2026-09-06

## BEFORE THIS WEEKEND
- The owner-camera system existed, but the new Montrose shoreline camera was not yet passing the same cloud metadata/latest-image integrity audit as the other five.
- The sensing upgrade lived on a diverged branch rather than canonical `main`.
- Historical calibration was thin: six canonical confirmed modern events were available before this weekend's historical recovery.
- Public cameras were useful but ad hoc; source identity, rights, ROI, freshness and mirror-deduplication were not yet one canonical policy.
- Water-quality ingestion existed, but production predictive validity was not established and observation-effort controls were absent.
- River forcing, source discovery, feature governance and model-validation architecture were less complete.

## COMPLETED THIS WEEKEND
- Merged PR #2 safely into `main` with a normal ancestry-preserving merge; no shared-main force push.
- Resolved the Montrose shoreline audit mismatch. All six owner cameras now pass metadata/latest-image integrity; both physical site groups pass.
- Point-in-time desktop acceptance verified 6 captures, 6 vision outputs, 6 live publications, 18 burst archive images, 28 R2 hash-verified objects and HTTP 200 for the shoreline image.
- Added/updated canonical camera registry, public-camera observation-only policy, retention policy, sensing audit and coverage dashboard.
- Added one normalized data contract, one validation contract and one feature catalog with explicit promotion/rejection states.
- Consolidated new ongoing-data discoveries into the canonical source registry and removed the temporary discovery queue.
- Preserved ongoing live camera commits after the merge, demonstrating the publisher continues to coexist with model/code history.

## DATA NOW KEPT
- River forcing: 30,635 normalized rows; 4,588 discharge, 4,597 stage, 21,450 gate-related; 20 distinct series/method combinations.
- Water quality: 7,650 normalized observations across 9 stations; 3,417 ADEM beach rows and 4,233 Alabama Water Watch Magnolia rows, with immutable compressed raw archives and SHA-256 provenance.
- Historical/event matching: 86 unique event-linked water-quality observations; 5 same-day pairs excluded to prevent leakage.
- Camera architecture: six owner cameras retained in expected-device health, with private archive/public publication policy and site-level independence grouping.
- Registries/contracts now preserve source class, coordinates/station IDs, observation-vs-model/proxy status, depth/datum, units, QC/health, freshness, rights/access, provenance and ingestion status.

## HISTORICAL EVENT DATA ADDED
Canonical confirmed-event count increased from 6 to 11. New historical positives include:
- July 1959 Point Clear / roughly four miles south of Grand Hotel; one-day date ambiguity retained rather than falsely resolved.
- August 15, 1972 Daphne–Montrose corridor; pre-dawn, one-to-two-hour archival event.
- August 12, 2010 Point Clear; same-day first-person relay with coordinates and species.
- August 16, 2013 Point Clear; same-day first-person photo report.
- July 24, 2025 Fairhope; separate event from July 17.

The historical source registry also preserves unresolved leads rather than converting them into labels: Loesch 1946–1956 event set, May 1971/1973 oxygen profiles, 2013 and 2017 event-window leads, early newspaper history and social/news source chains.

## MODEL/VALIDATION CHANGES
- No production forecast weights changed.
- Formal target decomposition now separates event occurrence by cell/window, intensity, duration and shoreline extent.
- Formal latent-state design separates `hypoxic_water_available`, `shoreward_transport_alignment`, and `nearshore_contact_and_detectability`.
- Defined benchmark/model comparison set: expert baseline, seasonal/persistence baseline, regularized logistic/discrete hazard, GAM/monotonic splines, hierarchical shoreline-cell hazard and three-state dynamic model.
- Defined held-out validation: leave-one-independent-event-out, blocked adjacent event days, season/year holdout when possible and geographic sensitivity.
- Metrics now include Brier score/skill, log loss, calibration, reliability, discrimination, event recall, false-alert burden, useful lead time, shoreline error and decision utility at the 20% threshold.
- 57 offline regression tests pass with 0 failures, 0 errors and 0 skipped.
- Forecast skill remains `NOT_ESTABLISHED` because verified matched non-event controls = 0.

## WHAT DID NOT HELP
- Generic `camera_negative` is rejected as a model feature; no detection applies only to the visible area/time and detectability.
- Social repost count is rejected as independent evidence.
- GCOOS is retained as a discovery/cross-check aggregator, not an independent predictor when it mirrors original providers.
- BOEM/BSEE platform inventory remains low-value until a suitable near-Mobile metocean/ADCP feed is identified.
- Enterococcus/beach bacteria remain zero-weight: they are runoff/fecal indicators, not oxygen measurements, and existing event/control coverage does not justify promotion.
- Upstream river flow remains a forcing proxy, not direct Bay-arrival state; no hard-coded lag was promoted.

## BLOCKED/UNFINISHED
- No continuous co-located Eastern Shore near-bottom DO + salinity + temperature sensors yet.
- Verified observation-effort matched non-event controls remain at zero.
- P0 physical datasets are registered but not normalized/ingested: NCEI 0188979 Mobile Bay moored CTDs, NCEI 0224293 Middle Bay multi-depth 2019, West End CP/FOCAL, Main Pass CTD, Ralston 2021 plume/SAR payloads, historical HFR, Weeks Bay NERR and Gulf Hypoxia Watch subsets.
- Loesch's primary event table and May's underlying dated station/profile data still require recovery/normalization.
- Fairhope/Grand Hotel public cameras remain observation-only unless rights permit retention; exact ROI/source-clock freshness remains incomplete for some views.
- The private-object-store permission/restore test was not independently re-run from the cloud after merge; prior desktop acceptance remains the current archive-integrity evidence.

## TOP 5 NEXT GAPS
1. Direct near-bottom DO + salinity + temperature at Montrose/Daphne and Point Clear — VERY HIGH value.
2. Historical event expansion plus observation-effort matched controls — VERY HIGH value.
3. Direct/validated local shoreward current/transport by shoreline cell — HIGH value.
4. Normalize the registered in-bay, mouth and shelf CTD/ADCP/HFR/hypoxia datasets — HIGH value.
5. Prospective public-camera ROI/freshness calibration and structured observations — MODERATE-HIGH value.

## THREE NEW IDEAS MOST LIKELY TO MAKE THE MODEL GREAT
1. **Event-process plus detection-process model.** Estimate the physical probability of a Jubilee separately from the probability that cameras/people/social sources would detect it. This attacks historical ascertainment bias directly.
2. **Low-oxygen reservoir and delivery digital twin.** Use direct bottom sensors plus multi-depth CTD, bathymetry, wind/water-level/current and plume state to estimate where hypoxic water is stored and ensemble-track whether it can contact each shoreline cell.
3. **Prospective high-information sampling.** When the model enters a favorable regime, trigger a standardized short field/boat transect or fixed multi-depth sensor sequence at Montrose/Daphne and Point Clear. This creates the clean event and non-event labels needed to turn the current scientifically grounded architecture into a calibrated predictor.

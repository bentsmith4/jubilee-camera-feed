# PR39 independent-year replication preregistration

Registered 2026-09-30, before any new oxygen–river association, model fit,
held-out error, or year-selection comparison. Repository summaries of 2016 and
2019 oxygen episodes were read; only the CSV headers of Meaher 2017 hydro/met
were inspected. Those prior summaries are not independent validation results.

## Question and scope

Does adding a fixed antecedent river-discharge window improve retrospective
out-of-year prediction of daily oxygen percent saturation at the **Meaher Park
station proxy**, conditional on contemporaneous local hydro/meteorology?
This is not a physical travel-time estimate, bottom-oxygen validation, shoreline
Jubilee validation, or dawn-available forecast. Unknown historical sonde height
remains a separate geometry gate. All river-lag production weights remain zero;
forecast probabilities, alert thresholds and production code remain unchanged.

## Fixed population and source selection

Use native DISL ARCOS Meaher Park (30.667152 N, -87.936459 E), 2017 training and
2018 untouched test, May 1–September 30 UTC in each year. These are the first two
complete calendar years after the already inspected 2016 episode, chosen by
calendar order and direct UTC source availability, not observed oxygen values or
skill. Do not switch years/stations after inspecting results. A failed coverage
gate produces a blocker, not a substituted favorable dataset.

Native annual links: https://www.disl.edu/arcos/ ; hydro `mp_hyd_sum.YEAR.csv.zip`
and met `mp_met_min.YEAR.csv.zip` under https://api.disl.edu/arcos/pregen/ .
Provider documentation labels downloadable timestamps UTC; oxygen `dis_oxy1_avg`
is percent, `dis_oxy2_avg` mg/L; do not mix them. Source flag 3 alone is accepted,
with finite values and documented physical ranges. Preserve source bytes hashes,
URLs, retrieval times, member hashes, schema, duplicate and exclusion counts.
Never borrow GCOOS's conflicting oxygen unit metadata.

Use USGS IV 02428400 Claiborne and 02469761 Coffeeville pool, parameter 00060,
monthly April–September batches. Preserve approved/provisional/estimated flags
through the existing normalizer. A single verified method per station/year is
required; no method mixing or interpolation. Coffeeville tailwater is not summed
with pool, and stage/gate data never substitute for discharge.

## Endpoints, controls and coverage gates

Primary target: daily median oxygen percent saturation, source flag 3 and 0–200%.
Retain at least 43 distinct valid half-hour observations/day, no gap over 1 hour,
including day edges; reject conflicting duplicate timestamps. Do not fill gaps.
Use identical held-out dates for each baseline/augmented pair.

Required same-day baseline covariates: log discharge; mean water temperature
(-5..45 C), salinity (0..40 PSU), mean water-height field `depth1_avg` and its daily
range; mean east/north wind components (knots converted to m/s, meteorological
FROM direction), air temperature (-10..50 C), solar radiation (0..1.5 kW/m2).
Water height is not sonde height above bed and not a stratification gradient.
Hydro controls need the same 43-sample/1-hour gate; depth must be finite positive
and flag 3 (no unsupported Meaher depth ceiling). Met controls require >=1296
unique valid minute timestamps/day and no gap >120 minutes, including edges;
wind direction 0..360 degrees and speed 0..30 m/s. Require each variable's flag 3.
Precipitation is excluded until its accumulation/interval semantics are resolved;
this leaves residual hydrometeorological confounding and prohibits causal claims.
No QC-unknown values are silently accepted.

USGS daily means require >=22 unique eligible observations in UTC day, no edge or
internal gap >2 hours, positive discharge, and one verified method. Each complete
antecedent window must exist. Both years need >=60 common-case days and >=6 fixed
14-day calendar blocks with >=7 scored days/block. Otherwise stop before fitting
and report exact per-variable/year coverage and joint overlap blockers.

## Frozen comparisons and fitting

Two prespecified co-primary comparisons, not a winner search:
1. Claiborne: antecedent offsets [7,8,9,10,11,12,13] days.
2. Coffeeville pool: offsets [3,4,5,6] days.
These reproduce PR39's half-open Python ranges; labels such as 7–14 must not be
misread as inclusive. Other windows are not tested in this replication.

Baseline: intercept + controls above. Augmented model adds log(mean antecedent
discharge). Use ridge penalty 1 on standardized slopes, unpenalized intercept;
means/scales fit on 2017 only, zero scale replaced with one. No tuning or selection.
Sensitivity: add annual sine/cosine calendar terms to both models (day-of-year /
365.25), plus a second sensitivity excluding USGS estimated/provisional values.
Freeze all coefficients on training year and score 2018 once. Do not fit a 2018
intercept or use 2018 oxygen to select features. Year separation exceeds the
14-day purge; no random folds, no cross-year shared upstream windows.

Report test RMSE, MAE, paired delta-MSE (augmented minus baseline), all fixed
14-day block delta-MSEs (anchored May 1), sample counts and exclusion ledger.
Negative delta-MSE means improvement. Report both comparisons regardless of sign.
For exploratory uncertainty use 10,000 seeded (39) resamples of paired 14-day
block sums/counts, reporting 97.5% percentile intervals for the two comparisons
(Bonferroni family-wise target 95%, approximate with few dependent blocks).
Do not claim effective independence of every day or of adjacent weather episodes.
No promotion follows even a favorable outcome: require geometry/maintenance
reconciliation, precipitation/shelf forcing sensitivity, further independent
replication and operational-availability validation. A proxy replication does not
validate the original three moorings' deployment-specific transport timing.

# PR39: independent-year oxygen proxy validation

## Decision

**The fixed river windows did not reproduce PR39's RMSE improvements in the
2017-training / 2018-test Meaher Park comparison.** Both increased test error,
including with calendar controls. This is independent-year evidence against
promoting those features, not proof of no physical river response. It is a
station-proxy replication, not a like-for-like replication of the three 2016
moorings. All river-lag production weights remain zero. No production source,
forecast probability, event label, alert threshold, or runtime setting changes.

Preregistration was published in commit
`20429b33a2449990cf5ffd971c34181c0d713a54` before fitting or inspecting lag results.
Only source schemas and existing repository research summaries had been read.
The audit first established coverage; each comparison requires BOTH years to
pass its coverage gate. Coffeeville's estimate-free sensitivity failed and was
not fitted. Failure of that sensitivity is not hidden by the primary result.

## Repository check and candidate search

Inspected PR39 head `e1d1c6b48fa966c7284dcda55fc22caaa5343366`, its September 30
independent review, and main snapshot `cbcff8edf2fe0457613daa7c2ab2c63d6c54fe89`.
An expanded local text search for oxygen/deployment, ARCOS, accessions and annual
source URLs **did find distinct-year references already in the repository**.
The important files agree across those two snapshots:

- `model_data/j09_data_access_upgrade_20260917.json`
- `model_data/j09_oxygen_episode_research_20260918.json`
- `model_data/j09_middle_bay_geometry_research_20260918.json`
- `model_data/ongoing_source_registry_20260906.json`
- `model_data/sensing_and_science_architecture.md`

Reproduce discovery with `rg -n -i '0224293|arcos|api.disl.edu|deployment' model_data`
(use the pinned snapshots to avoid later artifacts matching their own search).
No AGENTS.md was found in either inspected snapshot. No prior independent
river–oxygen year-held-out fit was located in these research references.

| Candidate | Evidence and disposition |
|---|---|
| NCEI 0188979, 0176497, 0190491, July 2016 | Same episode and sparse contemporaneous surveys. Not independent of PR39. |
| NCEI 0224293, Middle Bay 2019 | Already referenced/recovered: 4,409 QC-good rows, one delivered series, a roughly 84.8-day spring gap. Prior audit explicitly leaves timezone and depth mapping unresolved. Not silently joined to UTC forcing. Later 2021 sensor height cannot establish 2019 geometry. |
| Native DISL Meaher 2017/2018 | Selected by calendar order before looking at response relationships. Direct UTC station-year files, dense oxygen and co-located controls; actual river overlap verified below. Unknown sonde height limits interpretation to station proxy. |
| Native Meaher/Bon Secour 2019; Battleship 2022 | Existing research summaries already inspect oxygen distributions. Bon Secour has prior plausibility cautions; Battleship sample is December only with null QC flags. Not substituted into this frozen comparison. |
| NCEI 0116496 (1989–1999), 0116390 (1991–1993) | Authoritative catalog describes near-monthly surveys / weekly daytime citizen samples, respectively. Useful climatology, not the dense daily response-window protocol. |
| NCEI 0202224 Fowl River 2018; 0277234 Mobile Bay/Mississippi Sound from 2020 | Additional catalog leads. Fowl River is tributary geometry; 0277234's dense continuous temporal suitability was not verified. Neither used or claimed unusable in general. |

Search sources: [DISL ARCOS native annual downloads](https://www.disl.edu/arcos/),
[DISL range/flag definitions](https://www.disl.edu/arcos/datarange/),
[NCEI ARCOS collection](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc%3ADISL_ARCOS),
[NCEI Middle Bay 2019](https://www.ncei.noaa.gov/archive/archive-management-system/OAS/bin/prd/jquery/accession/details/224293),
[NCEI 0116496](https://www.ncei.noaa.gov/archive/archive-management-system/OAS/bin/prd/jquery/accession/details/116496),
[NOAA ARCOS project record](https://www.fisheries.noaa.gov/inport/item/65549).
Public search and repository evidence establish candidate existence; only the
16 exact downloaded inputs in `coverage.json` underpin this scored test.

## Provenance, geometry, time, units and overlap

Provider is Dauphin Island Sea Lab, native Meaher Park ARCOS, nominal registry
coordinates 30.667152 N, 87.936459 W (upper Mobile Bay). Historical sensor
height above bottom and maintenance/deployment changes remain unverified.
`depth1_avg` is a water-height/depth field in meters, not proof of sonde height.
No bottom-state, vertical-gradient or Eastern Shore contact inference is made.

DISL explicitly labels annual downloads UTC; every source timestamp is offset
aware and converted to UTC without guessing. Hydro is nominal half-hourly, met
minutely. Target `dis_oxy1_avg` is percent saturation; `dis_oxy2_avg` mg/L is NOT
pooled with it. Temperature is C, salinity PSU, solar kW/m2; winds convert knots
to m/s and meteorological FROM directions to east/north components. Flag 3 and
physical-range screening are required. The source flag scheme is not QARTOD's.

Native files span January–December in both years. Raw hydro rows: 17,448 in 2017,
17,280 in 2018; met rows: 524,730 / 517,903. Analysis uses May 1–September 30 UTC.
Each year has 152 eligible oxygen days; 2018 water-height coverage reduces the
joint set to 136. All five meteorological requirements pass 153 seasonal days.
No gaps, failed QC, conflicting duplicates, or antecedent days are imputed.

USGS 00060 is discharge in ft3/s, with April–September monthly IV inputs.
Claiborne uses method 2974, Coffeeville pool method 3121; methods are kept
separate. Approved/estimated status is retained. Pool/tailwater are never summed.
Historical records from an operational gauge do NOT establish what was published
before a historical dawn forecast cutoff. Same-day controls are retrospective.

| Comparison | Training days 2017 | Test days 2018 | Train / test eligible 14-day blocks |
|---|---:|---:|---:|
| Claiborne, offsets 7–13 inclusive | 152 | 136 | 11 / 10 |
| Coffeeville pool, offsets 3–6 inclusive | 108 | 136 | 9 / 10 |
| Claiborne, exclude estimated/provisional | 140 | 136 | 10 / 10 |
| Coffeeville pool, exclude estimated/provisional | **0** | 129 | **0** / 10 |

These offsets exactly preserve PR39's half-open Python ranges, not inclusive
7–14 or 3–7 labels. All 4,233 returned 2017 Coffeeville discharge rows are
estimated; removing them explains the zero-day sensitivity. 2017 Claiborne has
394 estimated rows; 2018 Coffeeville has 31; no provisional rows were observed.

## Held-out result

RMSE is oxygen saturation percentage points. Models include same-day discharge,
water temperature, salinity, water height mean/range, vector wind, air temperature
and solar radiation. Coefficients and scaling are fitted only on 2017. Annual
calendar sine/cosine is the frozen sensitivity. Both sides use identical dates.

| Comparison | Baseline RMSE | With lag RMSE | RMSE change |
|---|---:|---:|---:|
| Claiborne primary | 14.472 | 15.009 | **+3.71% worse** |
| Coffeeville primary | 13.736 | 16.287 | **+18.58% worse** |
| Claiborne + calendar controls | 12.145 | 13.564 | +11.69% worse |
| Coffeeville + calendar controls | 11.410 | 14.053 | +23.17% worse |
| Claiborne excluding estimates | 14.711 | 15.278 | +3.85% worse |
| Claiborne excluding estimates + calendar | 11.958 | 13.658 | +14.22% worse |
| Coffeeville excluding estimates | — | — | Blocked before fit: no training coverage |

Primary paired delta-MSEs (lag minus baseline): Claiborne +15.84, Coffeeville
+76.60. Approximate 97.5% paired-block percentile intervals: [-27.10, 69.49] and
[29.49, 133.52]. Claiborne worsens in 7/11 calendar blocks, Coffeeville 10/11.
All blocks with scored days are reported, including the final partial block;
coverage eligibility counts only blocks with >=7 scored days. These are
serial-data sensitivity intervals, not proof of independent daily samples.
Do not infer significance for all postulated mechanisms from two proxy tests.

Remaining scientific gates: exact deployment geometry/maintenance, precipitation
interval semantics, shelf forcing, oxygen-persistence baselines, additional
station/year replication, and actual forecast-cutoff availability. Salinity and
water temperature can also mediate river effects; this is conditional predictive
association, not a total causal-effect estimate. New stations/years must receive
a new preregistration, not be searched for a favorable replacement result.

## Reproduce and verify

Requires Python 3 and NumPy (recorded in results); other dependencies are stdlib.
From repository root:

```bash
python model_data/independent_river_validation/audit.py --cache-dir /tmp/pr39-independent --out model_data/independent_river_validation/coverage.json
python model_data/independent_river_validation/score.py --cache-dir /tmp/pr39-independent --coverage model_data/independent_river_validation/coverage.json --out-dir model_data/independent_river_validation
python -m unittest discover -s tests -p test_independent_river_coverage.py -v
```

The audit verifies downloaded hashes against an existing output manifest before
replacing it; changed provider bytes cause failure, not an unnoticed new result.
`coverage.json` records all source/member hashes, URLs, acquisition times, schema,
flags, excluded-row counts, missing-day reasons (nonexclusive) and exact common
dates. `score.py` checks cache hashes and preregistration hash, and rechecks date
coverage before fitting. `held_out_predictions.csv` allows error recomputation.
The six focused tests cover UTC boundaries, gap/duplicate/QC refusal, missing
antecedents, training-only scaling, and paired error/block calculations.
Source bytes are cached outside Git; source replay needs public network access.
Runtime audit timestamp and its linked digest change on rerun; scientific output
and prediction bytes should be identical with the same inputs/runtime.

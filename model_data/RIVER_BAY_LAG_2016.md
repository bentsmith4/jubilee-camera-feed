# 2016 river-to-Bay response-window study (research only)

## Decision

The archival USGS data are sufficient to test broad retrospective associations at **Claiborne discharge** and **Coffeeville pool discharge**, but not to calibrate a physical river-to-Bay travel time. Coffeeville tailwater discharge has zero returned 2016 rows in the three queried monthly batches. All dam-gate series likewise return zero 2016 rows. Pool and tailwater describe the same Tombigbee river and must never be added. No production weight, probability, or alert threshold changes.

## Reproduce

From the repository root with `requirements-model-data.txt` and `numpy` installed:

```bash
python model_data/research_river_bay_lag_2016.py --cache-dir /tmp/jubilee-river-2016 --out-dir model_data
python -m unittest tests.test_research_river_bay_lag_2016 -v
```

The script requests explicit June, July, and August 2016 USGS IV batches, passes them through `ingest_river_forcing.normalize`, and records source URLs, SHA-256 hashes, row counts, method IDs, and estimated/provisional counts in `river_bay_lag_2016_manifest.json`. It downloads and hashes the three NCEI 0188979 moorings and both canonical 2016 survey accessions. The cache holds source bytes locally; the tracked manifest identifies the exact input bytes. Reproduction should compare all hashes before accepting results if an agency republishes corrected data. Historical availability is retrospective and cannot be assumed at a 2016 forecast cutoff.

The fixed 0188979 moorings yield 9,014 raw records and 20 complete UTC days at each of three stations. Dissolved oxygen is **percent saturation**, not mg/L. Source time is explicitly CDT and converted to UTC with +05:00. Only dates with at least 100 valid 10-minute observations enter the daily median oxygen target. The 0176497 profiles have five survey dates and oxygen in mg/L with source clock labelled CST; 0190491 has three survey dates, oxygen in percent saturation, and one previously quarantined anomalous timestamp. Those sparse surveys corroborate in-bay coverage but do not supply independent temporal degrees of freedom for a lag fit; their units are not pooled.

Qualified hourly discharge uses one USGS method per gauge, with at least 22 observations on a UTC day and no interval or edge gap over two hours. Full antecedent windows are required; missing days are excluded rather than filled. USGS `e` and `P` qualifiers remain explicit. Claiborne has 2,205 qualified discharge timestamps and 90 complete days; Coffeeville pool has 2,207 and 91. The July batch contains 744 hourly discharge values at each station. There are **no** 2016 tailwater discharge or gate-opening values in the returned batches; tailwater stage does not substitute for flow.

## Held-out oxygen result

For each upstream series and predeclared window, fit station intercepts plus log same-day discharge (the no-lag baseline), then add log antecedent mean discharge for 1–3, 3–7, or 7–14 days **strictly before** the target day. Four contiguous date folds hold out all three moorings together with a one-day train embargo. The same 20 days and 60 station-days enter both sides of each comparison. Ridge scaling is estimated on training rows only. This is a descriptive comparison with a contemporaneous baseline, not a deployable dawn forecast.

| Gauge | Antecedent days | No-lag RMSE | Plus lag RMSE | With calendar trend: no-lag → plus lag RMSE |
|---|---:|---:|---:|---:|
| Claiborne | 1–3 | 35.51 | 36.46 | 44.64 → 31.60 |
| Claiborne | 3–7 | 35.51 | 36.63 | 44.64 → 57.06 |
| Claiborne | 7–14 | 35.51 | 31.61 | 44.64 → 32.43 |
| Coffeeville pool | 1–3 | 33.02 | 32.35 | 45.23 → 50.09 |
| Coffeeville pool | 3–7 | 33.02 | 30.92 | 45.23 → 40.67 |
| Coffeeville pool | 7–14 | 33.02 | 34.48 | 45.23 → 40.94 |

RMSE units are oxygen percentage points. The full JSON also reports station-specific results and leave-one-day-out error-difference ranges. Claiborne 7–14 days has a lower error at all three bay moorings against the simple baseline. Coffeeville pool 3–7 days improves the pooled simple baseline, but station 02 worsens. Calendar-trend adjustment radically changes several estimates and even reverses Coffeeville pool's 1–3 day result. Dates are adjacent within a single persistent oxygen episode; leave-one-day-out ranges are sensitivity diagnostics, **not** confidence intervals or independent replications.

## Scientific limit and next gate

The three moorings cover about three weeks in one summer. A smoothed upstream series, shared weather, tides, seasonal trends, local mixing, and autocorrelated oxygen can all produce apparent lags. Multiple windows and two gauges were examined; selecting the smallest error after seeing held-out results would leak model selection. These data justify testing broad **1–14 day antecedent response windows**, while no specific arrival time, uncertainty interval for physical travel time, or causal oxygen effect is identified. The survey profiles are too sparse to resolve that uncertainty. A separate year or deployment, contemporaneous hydrometeorological controls, and preregistered windows are needed before a travel-time claim or feature promotion. The 2016 result cannot validate Jubilee event prediction or shoreline contact.

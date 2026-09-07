# Science and model-validation review — September 6, 2026

## What was actually completed in this change set

- Added a tested expected-camera audit, including the new owner-reported Montrose shoreline camera as pending, not commissioned.
- Re-executed WQP ingestion with source-schema checks, explicit censoring/status distinctions, station metadata and immutable raw public archives.
- Corrected the exploratory diagnostic: strictly pre-event dates, unique-observation counts, geographic matching only when explicit, no invented negative labels, and no automatic production promotion.
- Implemented and executed USGS ingestion for Claiborne 02428400, Coffeeville pool 02469761 and tailwater 02469762. Kept 14 gate methods separate and preserved estimated/provisional qualifiers. Created gap-aware 1/3/7/14-day volume features. These are upstream research forcings, not a calibrated bay-arrival or Jubilee predictor.
- Created six-cell coverage and operational-readiness outputs. Local desktop deployment, Google authorization and public-camera recording remain separate acceptance gates.

The exact row counts, timestamps and test results are generated in `upgrade_readiness.json`, not copied into this document as an evergreen claim.

## Correction to the previous water-quality finding

The prior statement that bacteria probably does not help the model went beyond the test. The old comparison admitted samples from the event date, counted the same observation repeatedly across overlapping windows and used unreported dates as apparent controls. It had no validated forecast-availability timestamps and no complete station/event mapping. A lack of a stable difference in that analysis is not a valid demonstration of no predictive benefit.

Current conclusion: **INSUFFICIENT_VALIDATION**. The new code keeps production weights unchanged and reports these limitations. Six recorded positive dates do not establish forecast skill, and a large number of sensor rows is not a large number of independent events.

## Primary science reviewed and how it changes the research plan

### 1. Liu, Lehrter, Dzwonkowski, Lowe and Coogan (2022): wind, stratification and oxygen variance

Sources:
- https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2022.989017/full
- https://repository.library.noaa.gov/view/noaa/56083

Review scope: abstract, methods description and conclusions; no reimplementation of the authors' numerical model is claimed.

The study uses a high-resolution three-dimensional Mobile Bay simulation for an April–May 2019 hypoxic episode. Its oxygen-variance framework separates physical mixing and biogeochemical demand. It identifies sediment oxygen demand and vertical dissipation as major terms; a non-extreme southeast wind event can dissipate hypoxia and shift its location. A binary thunderstorm flag or one fixed wind-speed cutoff is therefore too crude.

Experiment to implement next: compare wind impulse and duration, salinity stratification, time since mixing, and observed DO recovery/decline against the current simpler wind feature. Test episodic hysteresis: identical current wind can have different implications depending on the preceding water-column state. Do not infer a DO profile from wind alone. The 2019 observation/model history is a targeted data-recovery lead, NOT marked ingested by this review.

### 2. Ralston, Geyer, Wackerman, Dzwonkowski, Honegger and Haller (2024): overlapping tide/wind/discharge control of Mobile Bay plume

Source: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024JC021288
Data references: https://doi.org/10.5281/zenodo.10659126 and https://doi.org/10.26025/1912/67567

Review scope: abstract, plain-language summary and data-availability statement. The Zenodo payload was not successfully recovered in this session; discovery is not ingestion.

The study combines 2021 shipboard measurements, radar/satellite observations and hydrodynamic modeling. It finds overlapping rather than neatly separable forcing regimes. Alongshore wind advects the plume, and tide amplitude and discharge influence cross-shore extent. Upwelling/downwelling affects shelf and estuary salinity and the routing of discharge between outlets.

Experiment: evaluate current vectors, observed water-level tendency, lagged terminal-river discharge and wind-driven shelf conditions together. Explicitly represent Main Pass AND Pass aux Herons/Mississippi Sound, without imposing a fixed flow split from a literature average. Ocean-front or satellite surface patterns remain surface/boundary evidence, never direct Eastern Shore bottom oxygen.

### 3. NOAA Gulf Hypoxia Watch / SEAMAP: historical shelf-bottom oxygen

Source: https://www.ncei.noaa.gov/products/gulf-america-hypoxia-watch

The product provides bottom-oxygen information associated with seasonal survey sampling. It is a better targeted historical shelf-oxygen lead than assuming an arbitrary oil/gas platform has oxygen sensors. Next task: recover dated stations within the Alabama/Mississippi shelf footprint, preserving depth, instrument and survey timing. Status here: primary source located; records NOT ingested. Seasonal cruise observations are not same-night sensors.

### 4. Platform, satellite and hydrographic priorities

Do not score a platform location as a measurement. Require an actual public data stream, sensor depth, variable, timestamp, QC and geographic relevance before adding a BOEM/BSEE/GCOOS platform source. Nearby ADCP/wave/wind records may improve boundary transport; distant platforms and surface-only data do not establish local hypoxia.

The remaining highest-value physical gap is still paired near-bottom DO, salinity and temperature near Montrose/Daphne and Point Clear. ARCOS/NERR/NGOFS2 and shelf products need explicit station/depth/source integration audits before being counted as operational coverage. Historical source discovery in earlier architecture documents is not evidence that their rows have been ingested.

## New model-effectiveness ideas, with acceptance criteria

1. **Decompose the target.** Predict occurrence, intensity, duration and shoreline extent separately. Crowd size, fish size and a poster's adjective are not interchangeable measures of intensity.
2. **Use a dynamic state sequence.** Oxygen stress/storage, mixing/restratification and delivery-to-shore are separate mechanisms. Compare a state-dependent model with simple seasonal, persistence and wind/tide baselines.
3. **Treat the observation process as part of the model.** Visibility, camera angle, report delays, observer effort and access outages affect apparent event frequency. Maintain deliberately sampled low-risk controls.
4. **Prevent human-sensor feedback.** More flashlights may mean locals read a forecast or a Facebook post. Use these as soft nowcasting evidence, not independent physical causation or proof that an earlier forecast was skillful.
5. **Use hydrologic topology.** Upstream tributary gauges, terminal gauges and pool/tailwater gauges overlap. Never sum nested gauges. Estimate travel-time kernels and uncertainty against downstream salinity rather than hard-code a universal lag.
6. **Archive prediction-time knowledge.** Save forecast issue time and exact input snapshot BEFORE outcomes are labeled. Reject post-event measurements and late lab results from prospective validation.
7. **Measure useful skill.** Report held-out Brier skill/calibration, recall, false-alarm burden, location error and useful warning lead time. Block adjacent event days and whole seasons to avoid near-duplicate leakage. Improve a metric before claiming the model became more accurate.

## Efficiency and data preservation

Keep deterministic baseline camera sampling plus selective higher-frequency acquisition. Use cheap image-quality/frozen-frame checks before expensive ROI vision. Share a per-device acquisition service but keep single-frame live and canonical temporal-burst products separate. Reuse a validated current-state snapshot across sensing/dawn reporting rather than re-downloading every historical source on every run.

Retain raw public data by hash and exact request; preserve private event AND control imagery in the existing verified private archive. The Git public archive is a bounded bootstrap; migrate before the configured size limit rather than allowing unbounded code-repository growth. No archival deletion was enabled by this change.

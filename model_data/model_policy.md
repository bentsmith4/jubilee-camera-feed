# Jubilee production-model policy — version 2

## Operational and scientific status

The four operational responsibilities are defined in `operations_contract.json`.
That document is not proof the Windows or ChatGPT schedulers have been changed.
The broader sensing/science architecture lists source domains; those are not
independent predictors that can be summed or multiplied.

The current water-quality analysis is an exploratory diagnostic, NOT evidence
of calibrated forecast skill. Earlier numerical probability estimates must not
be described as empirically validated unless an actual held-out validation
record supports that claim. Label heuristic judgment as such. Do not publish
precise percentages when inputs conflict or model calibration is absent.

## Evidence separation

Keep these five existing scoring families distinct:

1. Load / oxygen stress: direct LOCAL bottom DO, salinity and temperature first.
   Fish River, Weeks Bay, Magnolia River and offshore measurements are proxies
   at their actual geometry, not substitutes for Fairhope/Point Clear bottom DO.
2. Transport / delivery: observed or modeled currents, water-level tendency,
   wind and mixing. NOAA 8733821 astronomical tide is context, not evidence of
   an operating observed gauge or an actual nearshore current.
3. Local geometry / detectability: shoreline orientation, bathymetry, camera
   view, darkness, glare, source freshness and missingness.
4. Biological / human observations: explicit event evidence separate from soft
   searching-light/people signals. No face identification or person tracking.
5. Antecedent watershed / water quality: discharge, rainfall and research water
   quality. Enterococcus is not oxygen or hypoxia; remote physical observations
   remain geographically tagged proxies. Newly ingested features have ZERO
   production weight until properly validated.

Each observation has one source identity and primary role. Mirrors, same-site
views, multiple lag windows, dam pool/tailwater and repeated reposts do not
become independent confirmations. Other source domains such as satellites and
platform sensors are tagged by measured variable, depth, footprint and direct
versus proxy role, not automatically granted another vote.

## Dynamic processes, not absolute shortcuts

Recent events may inform a decaying prior but cannot mechanically predict a
third event or override contrary transport/mixing evidence. Nominal tide clock
alone is not a veto when validated local tendency/current indicates otherwise.
Wind effects depend on duration, direction, stratification and circulation,
not solely a fixed wind-speed cutoff or whether a thunderstorm occurred.

Upstream discharge requires a travel-time model before being called bay arrival.
The two Coffeeville gauges represent one river, not separate additive inflows.
USGS P/e flags remain attached; source-documented estimates are research inputs
with uncertainty, not secretly upgraded to direct measurements. Separate each
gate's method ID and do not collapse gates with identical readings.

## Validation and retention

Preserve raw public source responses, hashes, station/method IDs, depth, units,
timezone/datum, collection time, publication/availability time, ingest time and
transform version. Status='Final' is not full sensor QC. Preserve detection
conditions and censored values rather than substituting an exact value.

No report, no model detection or poor camera visibility is NOT a verified
non-event. Keep a fixed baseline sampling schedule alongside adaptive capture,
record observation effort, and avoid training only on interesting mornings.
Searching activity may be caused by forecasts or social posts; it is not an
independent physical forcing. Archive forecasts before verification to prevent
look-ahead leakage.

Use episode/season-blocked evaluation, independently evidenced events, explicit
station/cell mapping, observed controls and available-at timestamps. Report
unique observations separately from repeated lag memberships. Evaluate Brier
score/calibration, false alarms, event recall, location accuracy and useful lead
time against simple baselines. Validate occurrence, intensity and spatial
extent separately; fish size or crowd size does not establish event magnitude.

The September 6 corrected diagnostic excludes event-day samples and will not
promote variables. The earlier statement that bacteria probably adds no value
is superseded: the available test is insufficient to determine predictive value.

No user-facing alert-threshold change is authorized. No new private camera
publication or deletion of archived data is authorized by this policy.

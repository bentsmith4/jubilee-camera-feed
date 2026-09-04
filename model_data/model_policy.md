# Jubilee production-model policy

Keep five evidence families separate through scoring and reporting:

1. **Load / oxygen stress:** direct local bottom DO and salinity when available;
   Fish River/Weeks Bay only as a regional proxy.
2. **Transport / delivery:** modeled/observed current direction and water-level
   tendency. NOAA 8733821 predicted tide is context, not a substitute for
   observed water level or current.
3. **Local geometry / detectability:** shoreline orientation, camera field of
   view, darkness, glare, freshness, and missingness.
4. **Human sensor:** people and searching lights as a soft precursor only.
5. **Antecedent watershed / water quality:** historical ADEM/EPA beach-monitoring,
   Mobile Baykeeper SWIM, and Alabama Water Watch observations may be used for
   research and matched-event/non-event backtesting. Enterococcus is a runoff /
   fecal-indicator proxy, not a hypoxia measurement. Magnolia River physical
   measurements are regional proxies, not Eastern Shore bottom measurements.
   These features carry **zero production forecast weight** until they show
   defensible out-of-sample incremental predictive value.

A substantial confirmed event followed by a smaller confirmed next-morning
event raises the short-term prior through a decaying persistence term. It does
not mechanically predict a third event. Persistence must decay each day and
cannot override contrary transport, mixing, or direct oxygen evidence.

Nominal tide phase is one transport feature. Do not apply a hard veto from the
tide clock alone when observed water-level tendency or modeled current indicates
different nearshore transport. Missing or stale inputs widen the forecast
interval rather than being silently replaced with their last values.

All external water-quality ingestion must preserve raw observations and source
provenance before feature engineering. Do not silently merge observations from
different depths, stations, methods, or source classes.

No user-facing alert threshold change is authorized by this policy.

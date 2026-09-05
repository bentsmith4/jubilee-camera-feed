# Jubilee sensing and science architecture

Purpose: make the Jubilee model an explicit multi-layer observing system rather than a collection of ad hoc inputs. Every source below must remain tagged as observation, model guidance, historical research, or proxy. No source may silently substitute for another physical quantity.

## 1. Biological / human-observation layer

Primary use: direct evidence of an event or immediate precursor behavior.

- User cameras: Montrose and Point Clear Landing, with hourly temporal bursts plus near-live corroboration.
- Public nearshore cameras to integrate operationally from desktop: Fairhope Municipal Pier; Grand Hotel / Fleischer Pier / Point Clear; Daphne / Mobile Bay Delta; additional validated Eastern Shore feeds.
- Human-sensor features: pre-dawn flashlights, people walking/searching shoreline, clustered/focused search behavior. Treat as a weak precursor only.
- Same physical camera rebroadcast on multiple websites counts once.
- Social evidence: first-person public photo/video reports, with source independence, exact/approximate location, post time, claimed event time, species, behavior, and media preserved.

## 2. Local bay hydrography / oxygen-stress layer

Highest-value physical evidence is direct near-bottom DO + salinity + temperature in the Eastern Shore cells. Until those sensors exist, keep regional and mid-bay proxies explicit.

Priority public sources:

- DISL ARCOS, operating since 2003. Current station network includes Battleship Park, Bon Secour, Cedar Point, Dauphin Island, Meaher Park, Middle Bay Lighthouse, Middle Bay AWAC, Perdido Pass, Weeks Bay NERRS, Sofar Buoy, and West End CP. Historical annual met/hydro downloads are available from api.disl.edu. Hydro variables include water temperature, salinity, depth/pressure, dissolved oxygen mg/L and percent, and turbidity.
- Middle Bay Lighthouse / Middle Bay AWAC: central-bay hydrography and current structure; especially useful for detecting stratification, mixing, and transport states. Treat station outages explicitly.
- West End CP / offshore FOCAL site: ~9 nautical miles south of Dauphin Island; real-time offshore salinity, temperature, and dissolved oxygen are a high-priority boundary-condition input for the bay/shelf system.
- Weeks Bay NERR: regional southeast-bay oxygen/salinity state; proxy, not Point Clear/Fairhope bottom DO.
- Historical DISL / Alabama Marine Resources Division station records used in published Mobile Bay hypoxia research; recover station-year files wherever possible.

Research basis to encode:

- Mobile Bay summer hypoxia is fundamentally tied to salinity stratification and low-oxygen bottom water.
- Wind-driven upwelling/downwelling can materially alter hydrography and DO in the bay.
- Non-extreme winds can cause substantial DO variance; storm and wind mixing/restratification must be treated dynamically rather than as a static wind threshold.
- Bathymetric sinks, shoals, spoil fields, and the ship channel affect low-oxygen storage and delivery to shore.

## 3. Transport / bay-mouth / shelf-exchange layer

Jubilee prediction should represent how low-oxygen water is delivered to an Eastern Shore cell, not merely whether low oxygen exists somewhere.

Priority sources:

- NOAA CO-OPS Point Clear station 8733821: authoritative astronomical tide predictions and observed water level when available; keep predicted tide and observed level distinct.
- NOAA CO-OPS / NDBC Dauphin Island station 8735180 (DILA1): bay-mouth water level, winds, air pressure, and sea temperature.
- NOAA NGOFS2: modeled water level, currents, salinity, and temperature for Mobile Bay and adjacent shelf; label as model guidance, never observation.
- DISL Middle Bay AWAC: direct current-profile information when operational.
- DISL Sofar Spotter buoy near the bay mouth: wave height, wave direction, surface temperature, and pressure.
- Mobile Bay plume work (Ralston, Geyer, Wackerman, Dzwonkowski, Honegger, Haller, 2024): tides, wind, and river discharge have overlapping control on plume size/location; plume area can vary >5x and front position >10 km. Use this to replace simplistic tide-clock logic with current/water-level tendency + wind + discharge interactions.
- Ralston 2024 open dataset (Zenodo DOI 10.5281/zenodo.10659126) and associated 2021 SAR imagery dataset (WHOI DOI 10.26025/1912/67567): ingest for historical plume/transport calibration.
- Mississippi Bight HF-radar surface current data (GRIIDC DOI 10.7266/N7MS3QRM, 2010-2014) and any current IOOS/GCOOS HFR streams: use for shelf-current context and boundary conditions.
- Historical FOCAL site CP mooring: surface/bottom salinity-temperature and ADCP current profiles on the 20-m isobath offshore of Mobile Bay. Recover available historical records for stratification and shelf-exchange calibration.

## 4. Watershed / freshwater-load layer

Freshwater input affects stratification, residence time, nutrient/organic load, and plume dynamics. Upstream discharge must be lagged/propagated rather than treated as instantaneous bay inflow.

Priority real-time gauges:

- USGS 02428400 Alabama River at Claiborne Lock & Dam: discharge, stage, and gate openings; long daily-discharge history from 1975 and instantaneous data from 2007. Note that computed discharge excludes uncontrolled flow over the dam at very high stages.
- USGS 02469761 Tombigbee River at Coffeeville Lock & Dam: discharge, stage, and gate openings; long daily history from 1960 and instantaneous data from 2007.
- USGS 02469762 Tombigbee River below Coffeeville Lock & Dam: downstream discharge/stage; useful to reconcile dam-operation effects.
- Add upstream Coosa, Tallapoosa, Cahaba, and upper Tombigbee gauges only as antecedent/forecast forcings with empirically estimated travel-time lags.
- USACE ACT / Alabama-Coosa-Tallapoosa and Tombigbee water-control information: use gate/dam operations as explanatory forcing, not direct bay flow unless reconciled with downstream gauges.
- Historical lower Mobile/Tensaw distributary measurements, including Causeway studies and USGS/USACE archives, to estimate how Alabama/Tombigbee inflow partitions among Mobile, Tensaw, Apalachee, and Blakely pathways.

Derived features to test:

- 1/3/7/14-day integrated freshwater volume at Claiborne and Coffeeville.
- Alabama:Tombigbee flow ratio.
- Rate of change / hydrograph slope.
- Gate-operation transitions and pulse timing.
- Propagated lower-bay freshwater-arrival estimate with uncertainty.

## 5. Gulf / offshore / oil-platform observing layer

Use offshore observations to characterize the shelf boundary condition, mixing, waves, and current regime feeding Mobile Bay. Do not assume an oil/gas platform is useful solely because it exists.

Priority sources:

- DISL West End CP offshore hydrographic station (highest local value).
- NOAA/NDBC offshore buoys such as station 42012 when operational for winds, waves, and SST.
- GCOOS/IOOS observing feeds and historical Gulf platform metocean records.
- BOEM/BSEE platform-location inventory for identifying platforms near the Alabama/Mississippi shelf and determining whether they host public ADCP/metocean sensors.
- BOEM-funded platform current-monitoring datasets: platform-mounted ADCP systems can provide real-time current-velocity profiles and water level and have historically fed NOAA/GCOOS. Treat each station based on actual public accessibility and distance to Mobile Bay, not generic platform status.
- Rig/MODU operational metocean feeds are relevant only if public, spatially close enough, and consistently archived.

## 6. Satellite / spatial-observation layer

Satellites can fill spatial gaps that point sensors cannot, but they mostly observe surface conditions.

Priority sources:

- NOAA-20/NOAA-21/SNPP VIIRS ocean color: chlorophyll-a, remote-sensing reflectance, Kd490/KdPAR, true color. Use as surface productivity, turbidity/optical-water-mass, and plume-front features; not as bottom DO.
- NOAA/AOML Gulf products: daily SST, ocean color, altimetry-derived currents/sea-surface height, and numerical-model surface/subsurface currents.
- Synthetic Aperture Radar: use Mobile Bay plume/front datasets and future available SAR scenes to map plume boundaries under cloud cover where feasible.
- NASA/NOAA sea-surface salinity products where coastal resolution/quality is adequate; validate against in-situ salinity before use.

## 7. Bathymetry / geometry / dredging layer

Static and slowly changing local geometry strongly affects where hypoxic bottom water pools and contacts shore.

- NOAA bathymetry and navigation-channel geometry.
- USACE dredging/channel-maintenance records and spoil placement.
- Historical vs current bathymetry around eastern-shore contact zones.
- Local user observations such as dredging under the boat lift should not be generalized to regional geometry without survey support.
- Explicit shoreline-cell geometry for Fairhope Pier/Pecan, Fly Creek/Yacht Harbor, Montrose, Battles Wharf, Point Clear/Grand Hotel, Mullet Point, May Day/Village Point, and Daphne.

## 8. Scientist / publication watch list

High-priority researchers whose current and historical work should be continuously mined for datasets, methods, and new results:

- Brian Dzwonkowski, Dauphin Island Sea Lab / University of South Alabama — physical oceanography; tides, winds, river discharge, circulation, stratification, satellite sensors, numerical models, shelf monitoring and hypoxia.
- John Lehrter, Dauphin Island Sea Lab — hypoxia, dissolved oxygen variability, eutrophication, biogeochemistry, Gulf/estuary modeling.
- Ruth H. Carmichael, Dauphin Island Sea Lab / University of South Alabama — Mobile Bay hypoxia impacts, oysters, nutrient loading, estuarine ecology.
- David K. Ralston, Woods Hole Oceanographic Institution — Mobile Bay outflow plume, tides/wind/discharge interactions, open 2021 plume datasets.
- William R. Geyer, Woods Hole Oceanographic Institution — estuarine circulation and plume dynamics; collaborator on Mobile Bay plume work.
- Uchenna Nwankwo / Stephan Howden, University of Southern Mississippi — Mississippi Bight HF-radar and shelf-current dynamics.
- Josh Goff and DISL ARCOS operations/data team — observing-network continuity and station metadata.

## 9. Production evidence hierarchy

For daily forecasting, keep these families separate through scoring:

1. Direct local bottom oxygen/salinity/temperature.
2. Transport/delivery: observed/model current, water-level tendency, wind, bay-mouth/shelf boundary state.
3. Freshwater/stratification forcing: lower Alabama/Tombigbee discharge and lagged watershed state.
4. Local geometry/detectability.
5. Biological/human observations and public-camera signals.
6. Regional/offshore/satellite proxy state.
7. Historical priors/recent-event persistence.

A strong proxy must never override contradictory direct local observations. Missing direct data widens uncertainty; it is not automatically negative evidence.

## 10. Immediate implementation priorities

P0 — this weekend:

- Build a machine-readable source registry covering all sources above with source class, location, variables, cadence, access method, freshness, QC, and production eligibility.
- Add live USGS Claiborne + Coffeeville ingestion and 1/3/7/14-day freshwater-volume/trend features.
- Expand ARCOS historical ingestion beyond the currently used stations and audit station/depth/sensor-health periods.
- Recover the Ralston 2021 plume dataset and SAR metadata; determine which transport features can be calculated reproducibly.
- Inventory all validated public Mobile Bay cameras and classify them as nearshore biological, Eastern Shore environmental, or bay-wide context.
- Add a data-gap dashboard showing each shoreline cell's direct DO, salinity, current, camera, human-sensor, and report coverage.

P1 — next:

- Integrate public cameras from the desktop capture runner.
- Recover historical Middle Bay / FOCAL / May-era station data and align with verified Jubilee/non-event dates.
- Add VIIRS/SAR spatial features and HFR/shelf-current context.
- Estimate river-to-bay travel-time kernels empirically.

P2 — hardware gap:

- Deploy direct near-bottom DO/salinity/temperature at Daphne/Montrose and Point Clear. This remains the single largest sensing gap.

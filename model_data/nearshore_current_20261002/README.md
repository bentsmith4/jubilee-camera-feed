# Nearshore observed-current gap — 2 October 2026

**No suitable materially closer public dataset was verified. Zero new velocity
payloads were downloaded and zero Earth-frame rows were accepted.** This is a
bounded discovery/coverage result, not proof that no unpublished or inaccessible
Eastern Shore records exist. Jubilee-event predictive gain remains not estimable.

The baseline is calibration commit `c7acb9c0209f79d9bf6af85e4b590980cddcf9d0`
and checkout `3ab4b8c84843b04ed80b67b15671d68c2334fbb6`. PR38 is integrated
as research-only; its nearest navigation track is approximately 7.94 km from
the Point Clear reference, with all scientific rotation/motion/depth/time gates
still open. Its reproducibility result does not constitute current acceptance.
Existing source registry, J09 ingest/reconciliation and portable reviewed
reference were searched before public discovery. No existing source is promoted.

## Coverage findings

Distances are spherical great-circle calculations (Earth radius 6371.0088 km)
from the existing NOAA Point Clear reference 30.48664 N, 87.93453 W. This is not
an owner pier coordinate. Rounded station coordinates have corresponding spatial
uncertainty. A distance is not evidence of a common water mass or shoreline flow.

| Source | Distance to Point Clear | Verified evidence and limiting condition |
| --- | --- | --- |
| DISL Middle Bay site / GCOOS MBLA | 9.249 km | Dedicated AWAC is identified by DISL. Exact AWAC placement/configuration is not recovered; distance uses the MBLA site proxy. Mirror current speed/direction aggregate QC range is 9–9 (missing); depth is 0–0 m. A named current variable is not a valid current record. |
| NOAA active APM / ASPA / Cochrane | 22.608 / 27.293 / 29.241 km | Active inventory gives deployment dates and coordinates. Port/river geometry fails closer/local screening. Active deployment is not proof of fresh accepted samples. |
| NOAA 2010–2011 surviving survey moorings | 26.495–64.933 km | NOS CS 28 printed pp.17–19 (PDF pp.26–28 zero-based) gives orientation, depths, local-standard-time UTC−6 and 6-minute sampling. Four survived. No new sample QC or ingestion claimed. |
| NOAA lost MOB1103 / MOB1102 | 9.395 / 19.644 km | Printed p.19 Table 6 footnote and p.15 §4.1 identify lost instruments. A planned station cannot supply recovered observations. Table and footnote visually checked in the primary report. |
| GRIIDC spring-2016 mixing array, DOI 10.7266/N7Z036JW | 35.628–59.310 km | Six bottom moorings outside Mobile Bay; collection 29 March–15 April 2016. Landing page gives UTC MATLAB time, m/s u/v/w/error, depth bins, echo/correlation and percent-good diagnostics. Geometry fails; 28.33 GB payload acquisition would not close the local gap. |
| USGS mooring 392 | 21.986 km | Indexed temperature-package metadata give 30.296 N, 87.99533 W. Velocity package access blocked; temperature-package times are not assigned to current records. Full archive inventory remains unresolved. |

Primary URLs, coordinate precision, available collection/deployment times, units
and blockers are in `source_inventory.json`. `retrieval_receipt.json` hashes
four retained provider metadata snapshots. The NOAA active SOAP/SOS inventory
snapshot supplies all three current-station coordinates and deployment dates;
the historical inventory lists seven stations, consistent with the four surviving
survey sites and three retired PORTS sites in NOS CS 28. Its active inventory is
provider-generated at its own stated time, not a claim of October 2 sample freshness.

The MBLA metadata global coverage spans 2006-08-22 to 2026-04-14, while its
duration says P13DT18H. That inconsistency and current QC placeholders prohibit
claiming a continuous current series. Speed units are cm/s and direction is
`sea_water_to_direction`, degrees. Neither those labels nor constant zero depth
establish true-north correction or a valid near-bottom sampling volume. The
dedicated AWAC page has an embedded display with fixed February–April 2026 time
bounds; it does not establish operational freshness or a current-data export.

NGOFS2 can supply geographically close **modeled** currents; the existing
Point Clear model node is not an independent observation. HF radar surface
vectors, offshore FOCAL/AWAC records, tide predictions and water-quality sondes
are different measurements or proxies. None is silently relabeled as local
near-bottom observed current. No social silence or event/non-event labels were
used or modified by this audit.

## Protocol registered before new velocity inspection

`acceptance_contract.json` was committed separately in remote commit
`323d9e65334cf1d2031c27c955df7dc868922583`. Metadata discovery and existing J09
results were already known; **this is not a retrospective preregistration of
them**. No new velocity payload or favorable skill result was inspected.

The 5 km discovery screen, 1 km direct-local distance cap, 14-day commissioning
window, 90% coverage, 5-minute reporting, 30-second clock bound and uncertainty
targets are explicit provisional design choices, not NOAA standards or proof of
skill. Another Eastern Shore target requires separately registered coordinates,
shoreline geometry and acceptance scope before inspecting its vectors. A radius
alone cannot prove applicability. Candidate-specific manufacturer QC thresholds,
native burst settings, bathymetry and deployment/configuration evidence must be
locked before acquisition; they have not been invented in this metadata audit.

Required evidence before accepting a local vector:

- Immutable raw file hashes, instrument identity/configuration and deployment
  log; separate observed, available and ingested UTC timestamps. Document native
  clock/timezone/drift rather than inferring them from filenames or daylight time.
- Units, direction-to convention, heading calibration, pitch/roll and exactly
  once applied magnetic-declination correction; true east/north rotation checked
  against known cardinal vectors and independent installation alignment.
- Fixed mount stability, or independently documented vessel/platform motion
  removal. GPS course cannot replace compass heading. Retain original components.
- Surveyed horizontal sampling volume, bed clearance, transducer elevation,
  blanking/cell geometry and side-lobe/boundary masks; reject dry, buried,
  wake-obstructed and contaminated cells. Constant zero depth is insufficient.
- Instrument-specific QC and service/calibration flags. Missing/not-evaluated/
  suspect/failed observations remain unaccepted and UNKNOWN, never zero current.

These requirements follow the concerns described in U.S. IOOS QARTOD Currents
v2.1 (2019), DOI [10.25923/sqe9-e310](https://doi.org/10.25923/sqe9-e310),
especially §2.4 and Appendix B.3–B.5. Numeric design targets above are ours.

Source acceptance would still require a separate preregistered, availability-time
bounded, episode/day-blocked held-out loading-only/transport-only/combined Jubilee
test. The present absence of Tier-A controls prevents a defensible predictive
gain, false-alert, missed-event or lead-time estimate.

## Exact unresolved access and archival requests

The full USGS inventory and current-package metadata returned HTTP403 through
direct retrieval and web access. The alternate `cmgds.er.usgs.gov` metadata host
also failed; NCEI accession 0066111 landing-page access failed. Indexed snippets
can identify particular moorings, but cannot prove archive-wide absence. Request
the **complete 1990–1992 Mobile Bay mooring coordinate/deployment table and native
current records with compass, clock, units, depth and QC history** from USGS
CMHRP Woods Hole / NCEI accession 0066111. First filter within 5 km of the Point
Clear reference and separately list shallow Eastern Shore sites.

The primary Springer preview of Park/Kim/Schroeder (2007), DOI
10.1007/BF02782967, confirms summer-2004 shallow-water time series but exposes
no downloadable native current dataset or coordinate/configuration table in the
accessible preview. Methods require institutional article access; no purchase or
access approval is assumed. Request the **2004 shallow mooring station table and
native velocity files underlying that paper and the Hurricane Ivan study**, plus
any Point Clear/Montrose/Fairhope deployments, from DISL ARCOS's data architect
and physical-oceanography program. Include orientation/declination, clocks,
sampling volume, deployment and QC logs. The USGS/NOAA older circulation reports
remain additional archival leads, not accepted data. No messages were sent.

DISL ARCOS contacts and station pages are published at
[DISL ARCOS](https://www.disl.edu/arcos/). Request native Middle Bay AWAC export
and complete deployment metadata separately from the MBLA mirror. A closer
unpublished deployment might change the result; it is not presumed to exist.

## Minimum local measurement to close the vector gap

The existing sub-$1,000 hydrography design measures DO/salinity/temperature; it
does **not** measure current. A local addition needs a calibrated two-horizontal-
component current meter (or shallow-water-capable ADCP), with:

- An actual sampling volume approximately 0.15–0.30 m above the local bed,
  below ordinary low water, offset outside piling wakes/prop wash; final location
  surveyed and indexed. A single point meter closes only that site's bottom
  vector gap; vertical shear/transport requires a profile or additional level.
- True east/north velocity in m/s, native components, compass heading/variation,
  tilt and uncertainty records. Initial design targets are ≤0.02 m/s horizontal
  uncertainty and ≤5° heading uncertainty, confirmed over the relevant low-speed
  range. Do not assign a confident onshore sign when projected flow is within
  propagated uncertainty; shoreline-normal bearing must be separately surveyed.
- Five-minute records with documented burst averaging, UTC clock error ≤30 s,
  separate availability timestamps, immutable raw logging, battery/power and
  diagnostics. No forward filling through gaps or service windows.
- Automatic logging/telemetry with local buffering and recovery after Wi-Fi or
  power interruption. Use existing pier infrastructure where suitable. Routine
  predawn visits are not part of operation; daylight retrieval/cleaning and
  before/after calibration remain necessary.
- Fourteen commissioning days with ≥90% accepted expected records and no
  accepted gap >15 minutes, per-dawn coverage disclosure, independent alignment
  verification and drift/fouling checks. Passing this is measurement validation,
  not Jubilee predictive validation. Budget feasibility remains unverified.

One Montrose sensor cannot establish Point Clear currents. Each deployment has
its own geographical scope; uncertainty about either site remains explicit.

## Reproduce and review

From repository root:

```sh
python model_data/nearshore_current_20261002/audit_coverage.py
python -m unittest discover -s tests -p 'test_nearshore_current_coverage.py' -v
```

The offline audit verifies retained snapshot hashes and the registered contract
hash, then recomputes geometry. It never ingests velocities or produces accepted
rows. `coverage_result.json` is its reproducible output; tests compare exact
output and exercise missing/invalid geometry and the lost-instrument boundary.
All changes are new research files plus their focused test. Production code,
probabilities, weights, thresholds, forecasts, alerts and schedules are unchanged.

# Jubilee production-model policy — version 2.1

## Operational and scientific status

The four operational responsibilities are defined in `operations_contract.json`.
The broader sensing/science architecture lists source domains; those are not
independent predictors that can be summed or multiplied.

The current water-quality analysis is an exploratory diagnostic, NOT evidence
of calibrated forecast skill. Earlier numerical probability estimates must not
be described as empirically validated unless an actual held-out validation
record supports that claim. Label heuristic judgment as such. Do not publish
precise percentages when inputs conflict or model calibration is absent.

## Evidence separation

Keep these five scoring families distinct:

1. **Load / oxygen stress:** direct LOCAL bottom DO, salinity and temperature
   first. Fish River, Weeks Bay, Magnolia River, shelf and offshore measurements
   are proxies at their actual geometry, not substitutes for Eastern Shore
   bottom DO.
2. **Transport / delivery:** observed or modeled currents, water-level tendency,
   wind and mixing. NOAA 8733821 astronomical tide is context, not evidence of
   an operating observed gauge or an actual nearshore current.
3. **Local geometry / detectability:** shoreline orientation, bathymetry, camera
   view, darkness, glare, source freshness and missingness.
4. **Biological / human observations:** explicit event evidence separate from
   soft searching-light/people signals. No face identification or person
   tracking.
5. **Antecedent watershed / water quality:** discharge, rainfall and research
   water quality. Enterococcus is not oxygen or hypoxia; remote physical
   observations remain geographically tagged proxies. Newly ingested features
   have ZERO production weight until properly validated.

Each observation has one source identity and primary role. Mirrors, same-site
views, multiple lag windows, dam pool/tailwater, nested river gauges and
repeated reposts do not become independent confirmations. Other source domains
such as satellites, annual shelf surveys and platform sensors are tagged by
measured variable, depth, footprint and direct-versus-proxy role, not
automatically granted another vote.

## Dynamic processes, not absolute shortcuts

Recent events may inform a decaying prior but cannot mechanically predict a
third event or override contrary transport/mixing evidence. Nominal tide clock
alone is not a veto when validated local tendency/current indicates otherwise.
Wind effects depend on duration, direction, stratification and circulation, not
solely a fixed wind-speed cutoff or whether a thunderstorm occurred.

Upstream discharge requires a travel-time model before being called bay arrival.
The two Coffeeville gauges represent one river, not separate additive inflows.
USGS provisional/estimated flags remain attached; source-documented estimates
are research inputs with uncertainty, not secretly upgraded to direct
measurements. Separate each gate's method ID and do not collapse gates with
identical readings.

## Dawn visual assessment rule

The principal visual assessment must use the first completed and published
validated camera burst captured at or after local civil dawn. Do not base the
principal dawn assessment on an older pre-dawn dark burst merely because it is
the freshest available frame at run start. A burst is usable only when
freshness, timestamp matching, health and actual visibility/detectability pass.

If the first burst at or after dawn is still too dark or otherwise inadequate
for biological assessment, classify biological evidence as `UNKNOWN` and use
the first completed/published dawn+20-minute burst as the daylight follow-up
before making the principal visual call. Preserve overnight positive biological
signals, material physical/event alerts, and flashlight/searching/human
observations, but suppress repetitive user-facing updates whose only finding is
unchanged darkness or low detectability.

Apply the same dawn timing rule to public-camera observations.

## Public cameras — observation-only policy (PUBLIC-CAM-001)

Public-camera checks are observation-only unless the owner later grants separate
retention permission and the source's own rights permit retention. Use only
permitted public viewing paths; do not bypass access controls or automated-access
restrictions. Do not save, retain, archive, upload or persist screenshots,
thumbnails, video or image data from public cameras. Keep the six owner-camera
archives unchanged.

For each public camera actually viewed, retain only factual structured analysis:
- camera and physical-camera identity;
- public viewer URL;
- check time;
- source capture time and freshness basis when known;
- still versus video and observation duration;
- visibility, glare, darkness and visible shoreline scope;
- separate status fields for shrimp-like activity, diving/feeding birds, fish
  surfacing/gulping, swimming crabs, shoreline animal concentrations, people
  collecting, and searching/flashlights, each limited to `observed`,
  `not_observed`, `uncertain`, or `not_assessable`;
- concise supporting description for each relevant field;
- overall outcome limited to `event_evidence_present`,
  `no_event_evidence_in_visible_area`, or `unknown`;
- `media_retained=false`;
- `retrospective_visual_review_available=false`.

Motion claims require temporal evidence. Do not identify shrimp from ambiguous
specks. Birds or people alone do not confirm a Jubilee. Missing, stale, frozen,
dark or poorly visible public-camera views must be `unknown`. Rebroadcasts of
the same physical camera share one independence group. Do not invent historical
checks or contact camera owners.

## Validation, observation effort and retention

Preserve raw public source responses, hashes, station/method IDs, depth, units,
timezone/datum, collection time (`observed_at`), publication/forecast
availability time (`available_at`), ingest time (`ingested_at`) and transform
version. Status=`Final` is not full sensor QC. Preserve detection conditions,
censored values and missingness rather than substituting an exact value.

No report, no model detection or poor camera visibility is NOT a verified
non-event. Keep a fixed baseline sampling schedule alongside adaptive capture,
record observation effort, and avoid training only on interesting mornings.
Searching activity may be caused by forecasts or social posts; it is not an
independent physical forcing. Archive each forecast and its exact input snapshot
before outcome verification to prevent look-ahead leakage.

Use episode/season-blocked evaluation, independently evidenced events, explicit
station/cell mapping, observed controls and available-at timestamps. Report
unique observations separately from repeated lag memberships. Evaluate Brier
score, log loss, calibration slope/intercept, reliability, false alarms, event
recall, location accuracy and useful lead time against simple baselines.
Validate occurrence, intensity, duration and spatial extent separately; fish
size or crowd size does not establish event magnitude.

The September 6 corrected diagnostic excludes event-day samples and will not
promote variables. The earlier statement that bacteria probably adds no value
is superseded: the available test is insufficient to determine predictive value.

## Production promotion gate

No new feature receives positive production weight merely because it is
scientifically plausible or correlated in-sample. Promotion requires:
1. provenance/QC and an explicit physical interpretation;
2. sufficient independent positive and observed-control coverage;
3. no post-event leakage;
4. incremental performance in held-out episode/season validation;
5. calibration and decision-utility review at the alert threshold; and
6. a written promote/reject decision with versioned feature/model IDs.

No user-facing alert-threshold change is authorized by this policy. No automatic
archival deletion is authorized by this policy.

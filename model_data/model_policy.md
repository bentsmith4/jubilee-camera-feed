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

## Dawn visual assessment rule

The principal visual assessment must use the first completed and published
validated camera burst captured at or after local civil dawn. Do not base the
principal dawn assessment on an older pre-dawn dark burst merely because it is
the freshest available frame at run start. A burst is usable only when freshness,
timestamp matching, health, and actual visibility/detectability pass.

If the first burst at or after dawn is still too dark or otherwise inadequate for
biological assessment, classify biological evidence as `UNKNOWN` and use the
first completed/published dawn+20-minute burst as the daylight follow-up before
making the principal visual call. Preserve overnight positive biological signals,
material physical/event alerts, and flashlight/searching/human observations, but
suppress repetitive user-facing updates whose only finding is unchanged darkness
or low detectability.

Apply the same dawn timing rule to public-camera observations.

## Public cameras — observation-only policy (PUBLIC-CAM-001)

Public-camera checks are observation-only unless Ben later grants separate
retention permission. Use only permitted public viewing paths; do not bypass
access controls or automated-access restrictions. Do not save, retain, archive,
upload, or persist screenshots, thumbnails, video, or image data from public
cameras. Keep the six owner Google-camera archives unchanged.

For each public camera actually viewed, retain only factual structured analysis:
- camera and physical-camera identity;
- public viewer URL;
- check time;
- source capture time and freshness basis when known;
- still versus video and observation duration;
- visibility, glare, darkness, and visible shoreline scope;
- separate status fields for shrimp-like activity, diving/feeding birds, fish
  surfacing/gulping, swimming crabs, shoreline animal concentrations, people
  collecting, and searching/flashlights, each limited to
  `observed`, `not_observed`, `uncertain`, or `not_assessable`;
- concise supporting description for each relevant field;
- overall outcome limited to `event_evidence_present`,
  `no_event_evidence_in_visible_area`, or `unknown`;
- `media_retained=false`;
- `retrospective_visual_review_available=false`.

Motion claims require temporal evidence. Do not identify shrimp from ambiguous
specks. Birds or people alone do not confirm a Jubilee. Missing, stale, or poorly
visible public-camera views must be `unknown`. Do not invent historical checks or
contact camera owners.

No user-facing alert threshold change is authorized by this policy.

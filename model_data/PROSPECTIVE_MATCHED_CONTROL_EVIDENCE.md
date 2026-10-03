# Prospective matched-control evidence — October 2, 2026

Research only. Five candidate Tier-B mornings, zero verified Tier-A controls.
The October 2 audit at `98f81903d341e5f7415459fbf9eaed226cd1644f`
contains 12 cycle records (04:25:41–08:02:44 CDT), six low-light UNKNOWNs
and six later `CANDIDATE_VISIBLE_SCOPE_CONTROL` records. Cycle times are
not the actual shoreline frame times. Preserve the original audit and contract
blob `091f586f36902be96e9d1bd07ebfbfc19444303c` unchanged.

## What is missing

Tier A means a fully verified **matched** control, not simply a healthy camera
or a whole shoreline without reports. The existing contract permits an
unattended, adequately resolved camera-visible-scope negative without a human
field check. Whole-cell coverage, an independent second camera, and accessible
Facebook/Nextdoor are not universal prerequisites for that narrow label.

| Evidence category | Missing evidence and admission rule |
| --- | --- |
| Observation validity | Actual frame times, timing semantics, intact media, freshness/burst/vision binding, adequate biological detectability and a reviewable outcome in the claimed scope. The structured vision is not independent pixel review. Retain pixels and document later review/uncertainty rather than counting repeated automated assessments as independent observers. |
| Spatial and temporal scope | Fixed shoreline ROI or geometry reference shared with a confirmed event. A burst supports only sampled frames; darkness and the approximately 20-minute gaps cannot become a whole-morning negative. A full-window claim needs validated temporal coverage and detection sensitivity for the event class, or a documented continuous independent observation channel. |
| Event comparator | A confirmed event ID, its footprint, observed time/onset-duration uncertainty and comparable detection effort. The August 29 approximately 07:30 Sibley/Montrose report is not tied to the exact 437 segments. Do not invent a match. |
| Matching design | Before scoring, fix defensible tolerances for all eight contract dimensions: scope, season, clock window, tide, transport when available, and private/public/social-or-human availability. Record paired provenance and QC. Tide predictions are distinct from observed water levels. Transport unavailability can be an explicit limitation under “when available”; it is not an invented mandatory sensor. Unavailable public/social channels may be matched as unavailable only with a documented comparable event-side observation basis. |
| Validation design | Block by episode/date and assess serial correlation before held-out evaluation. Multiple bursts from one morning do not create independent controls. Later outcome review must never become an earlier forecast predictor. |

## Smallest unattended collection change

`matched_control_evidence.yml` runs on existing main capture commits and on
collector/workflow changes, so installation itself verifies packet publication
without waiting for or requesting another capture. It checks out the **triggering SHA**, not later main, and stores an immutable Actions
artifact keyed by SHA/run/attempt. There is no cron, production writer or
additional camera capture. All captures, including event signals, poor views
and outside-window captures, follow the same collection path regardless of
model risk. This preserves observation-process comparability.

`collect_matched_control_packet.py` retains status, burst and vision bytes,
the latest Montrose shoreline JPEG, the unchanged geometry/control contracts,
event/public observation records, and available environmental manifests plus
the state snapshot. It hashes every retained file, preserves actual shot times
and timing semantics, and flags missing files and unresolved pairing dimensions.
Context is pinned **checkout-time** evidence: timestamps, QC and `available_at`
still require reconstruction before claiming capture-time conditions. No
context is silently promoted to a paired tide/transport observation.

The Git mirror lacks the first two burst images. The existing desktop path
already seals three-frame captures locally and uploads them to R2. The packet
records the existing archive manifest key as **NOT_VERIFIED**; retrieve that
manifest and all three images and verify hashes/readback before pixel review
or asserting complete burst retention. A guessed key is not an archive receipt.
No new R2 credentials or archive writer is introduced here.

Artifacts expire after 90 days (subject to repository limits). Confirm the
workflow executes after merge; download/seal selected event and control packets
before expiry into the existing research/archive evidence path. Workflow
failure or an expired/missing packet is an evidence gap, never a negative. The
script can also run against an exact historical checkout with output outside
the repository. A delayed run retains the bytes but conservatively marks stale
inputs; it does not claim issue-time freshness.

The collector does not implement Tier-A admission or select tolerances. Every
packet starts with unresolved pairing, UNKNOWN biological/whole-window outcome,
zero training negatives, and no forecast eligibility. It creates reviewable
inputs for a later research admission decision, not a replacement event label.

## Exact camera blockers and minimum additional channel

| Target | Current blocker | Minimum unattended evidence path |
| --- | --- | --- |
| 437 Montrose, sampled usable-light scope | Waterline and cedar stumps are visible; no defensible confirmed-event pair yet. Earlier darkness and inter-burst intervals remain unknown. | Existing camera can support a narrow Tier-A pair once a confirmed event is documented in the same visible segments/time sampling and all match dimensions are reviewed. No additional camera or routine field visit is inherently needed. Recover/readback the existing burst archive for review. |
| 437 Montrose, whole predawn window | Full-dark biological detectability is inadequate and bursts leave long gaps. More daylight bursts cannot repair early darkness. | A timestamped, retained continuous shoreline-contact recording resolving the relevant fauna in darkness, with validated illumination/low-light detectability and coverage uptime. Reuse the current camera only if it can demonstrably supply those capabilities; otherwise add one appropriately placed low-light contact camera. Validate that illumination does not change animal behavior. Motion-trigger-only footage without measured miss sensitivity is insufficient. |
| Point Clear/Grand Hotel | Owner views look down marina/open Bay, not a close swash/contact strip. October 2 Grand Hotel player returned a client-side error on load/reload; no samples, capture clock or freshness established. Even accessible broad views do not repair geometry. | One accessible timestamped close beach/contact-strip recording channel for a declared Point Clear ROI, with adequate light/resolution, retained media and known coverage. This supports that ROI only. More viewpoints or known-effort independent coverage are needed for a larger cell claim. |
| Fairhope beach / Fly Creek | Public player shows pier, parking and broad water; neither beach nor Fly Creek is visible. Exact upstream capture delay remains unknown. | A directly aimed, timestamped retained channel for the particular beach/contact strip or Fly Creek target. Separate unseen targets require separate validated coverage; one pier view cannot establish both. |

Near-bottom DO/salinity/temperature or model guidance can improve environmental
matching, but cannot alone prove biological event absence. Naturally occurring
trusted-local observations may supply an additional documented observation
channel; routine owner predawn fieldwork remains unnecessary. Social searches
are corroboration and observation-effort logs only: no report, inaccessible
feeds, quiet people, or absence of flashlights never establishes a negative.

Probabilities, weights, thresholds, features, alerts, production labels and
all existing schedules are unchanged. There is no schedule-only change to
justify: the missing light/geometry/continuous evidence cannot be obtained by
merely increasing the existing snapshot cadence.

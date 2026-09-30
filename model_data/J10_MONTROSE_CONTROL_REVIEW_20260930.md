# Montrose matched-control review — September 30, 2026

**No Tier-A promotion is supported.** September 24, 26, 28 and 30 remain four
Tier-B candidate mornings. Held-out Jubilee-event calibration, missed events,
false alerts and lead time remain not estimable. Production probabilities,
weights, thresholds, features and alert behavior are unchanged.

The machine-readable companion is
`j10_montrose_control_verification_20260930.json`. It pins the requested
`d20eb5742ee37028f00833d25028fd17bfd892e9` audit and repository snapshot
`cbcff8edf2fe0457613daa7c2ab2c63d6c54fe89`, records source Git blobs and capture
commits, reconstructs actual primary-camera frame timestamps, and logs public
search effort and unresolved access gaps. Existing daily audits remain intact.

## What the evidence supports

| Morning (CDT) | Target-window capture cycles | Scoped non-event samples | Unknown samples | Decision |
| --- | ---: | ---: | ---: | --- |
| September 24 | 12 | 6 | 6 | Retain Tier B; no whole-morning negative |
| September 26 | 12 | 5 | 7 | Retain Tier B; 07:18 cycle remains unknown |
| September 28 | 12 | 6 | 6 | Retain Tier B; early low-detectability cycles remain unknown |
| September 30 | 12 | 6 | 6 | Retain Tier B; same-day reporting lag remains unresolved |
| **Total** | **48** | **23** | **25** | **Four candidate mornings; zero Tier A** |

The earlier audits explicitly cited 31 records: one on September 24, six on
September 26, and twelve each on September 28 and 30. The complete repository
scan reconciles 17 additional in-window records: eleven on September 24 and six
on September 26. They add five usable scoped observations and twelve unknowns,
not more independent mornings. Outside-window records are listed separately
and excluded. No new actual-event confirmation was found in the reviewed
repository or retrieved public evidence for these four dates.

The 23 research-only `observed_non_event_visible_scope` labels apply to the
actual sampled frames of the 437 waterline/beach segments visible in
`montrose_shoreline`. They use the existing validated three-frame vision and
integrity records, with moderate biological detectability, adequate visibility,
and no resolved visual or temporal Jubilee signal. This review did not perform
an independent pixel re-review. The labels do not assert that all biology was
absent, that intervals between frames/bursts were observed, or that a Jubilee
did not occur elsewhere or earlier that morning.

Capture-cycle time is not the primary-camera screenshot time. For example, the
September 24 06:36:53 cycle's actual shoreline screenshots were 06:38:31,
06:38:41 and 06:38:52 CDT. The JSON preserves all three timestamps per cycle.
The four-hour target windows must not be presented as continuous observation.
All whole-window outcomes in this review are `unknown`.

## Exact contract interpretation

`matched_control_contract.json` permits a fresh, unobstructed dawn shoreline
view with moderate/high detectability to support a **visible-scope** non-event.
It does not require independent human confirmation or whole-cell coverage for
that narrow label. Routine owner predawn checks are explicitly not required.
Thus the missing human/social confirmation cited in earlier audits is a
corroboration gap, not a new universal camera-label prerequisite.

Tier A additionally requires a defensible event/control match. All eight
contract dimensions are recorded separately for each morning: spatial scope,
season, clock window, tide, current/transport when available, and private,
public and social/human observation availability. No complete pair has been
established. Transport unavailability is an explicit limitation under the
contract's “when available” clause, not an invented absolute requirement.

The August 29 Sibley/Montrose trusted-local pocket is a possible event comparator,
but its approximately 07:30 report does not establish exact 437 camera geometry,
onset/duration, or comparable observation effort. A shared place name or nearby
season does not prove a match. Tide/transport reconstruction and a prespecified
matching tolerance remain unresolved. September 12's owner-scoped non-event
does not transfer to these dates; September 9 marina remains unknown.

## Public and local evidence review

Date-specific searches for each morning were supplemented by broader Montrose,
Fairhope and Mobile Bay queries, local-news domain searches, and Facebook and
Nextdoor discovery. No retrieved source provided date-specific event evidence
or a credible known-effort non-event confirmation for any of the four mornings.
This is a statement about retrieval, **not verified public silence**.

| Channel | Result and limitation |
| --- | --- |
| [Jubilee Watch Alabama directory](https://linktr.ee/jubileealabama) | Identifies relevant channels; not an event report. |
| [Facebook group](https://www.facebook.com/groups/3246895562306338/?ref=share) | Fetch throttled. Target-date posts unverified. |
| [Central Montrose Nextdoor](https://nextdoor.com/neighborhood/centralmontrose--fairhope--al/) | Public landing page and limited relative-date snippets only; no complete date-filtered feed. |
| [Jubilee Alabama website](https://www.jubileealabama.com/) | Fetch returned 502; verification gap. |
| Local news search | No qualifying target-date confirmation retrieved; WKRG robots block reported. Historical 2024 reports and unrelated festivals/businesses excluded. |

The owner's observation that real Jubilees normally leave a public trace is
useful corroborating evidence and motivates these searches. It cannot supply a
numerical absence probability without measured source coverage, reporting
sensitivity and lag. September 30 is particularly vulnerable to same-day delay.
No 80% absence assumption or silence-based negative is introduced.

Both arrays in `public_camera_observation_log.json` were checked. September 24
has two morning records in `observations`; September 26 and 30 have two each in
`records`. They are probably fresh broad Grand Hotel/Fairhope views with unknown
exact source capture time and `training_control_eligible=false`. They do not
observe the Montrose scope. September 28's eight overnight records and twelve
afternoon/evening observations fall outside its target window. Darkness,
ordinary pedestrian activity and quiet broad water are not shoreline negatives.

## What would allow further progress

1. Recover naturally occurring, date-specific local reports if they become
   accessible; retain author/source lineage, observed location/time, reporting
   time, observation effort and uncertainty. No routine owner fieldwork is needed.
2. Establish event-side observation geometry and availability comparable to the
   437 samples; reconstruct clock, season and tide/available transport matches
   before admitting a matched control. Do not choose tolerances to improve scores.
3. Once enough genuinely comparable independent episodes exist, use episode-
   blocked tests and assess serial correlation. Separate date counts alone do
   not establish independent statistical samples or permit held-out calibration.

All retrospective source checks are outcome-label review only. Neither later
reports nor camera availability/detectability becomes a pre-event physics
predictor. The added tests check provenance, coverage accounting, label bounds,
unknown preservation and the zero-promotion/leakage guards.

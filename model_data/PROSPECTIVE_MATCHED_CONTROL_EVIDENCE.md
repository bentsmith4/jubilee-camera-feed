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

## Selected packet sealing and durable readback — October 3, 2026

`seal_matched_control_packet.py` is a separate research-only GET consumer. The
original collector and its packet bytes remain unchanged, including the original
NOT_VERIFIED discovery pointer. An additional content-addressed receipt records
verified three-frame retention or EVIDENCE_GAP; this is archive completeness,
never Tier-A admission, independent pixel review, or a whole-morning label.

The operator explicitly selects an artifact ID, run ID, full capture-source SHA
and HTTPS public R2 base. The sealer checks Actions expiry and ZIP digest, every
retained-file hash, packet/capture/shot identity, R2 manifest capture ID and local
hash bindings, archived vision/burst metadata, all three frame hashes and sizes,
actual shot times and timing semantics, and the latest-image binding. It GETs
the manifest again to detect a changed archive. No latest pointer or new capture
is substituted. Missing hashes or unavailable legacy archives fail closed.

The create-only path is
`research/matched_control_archive/<receipt-sha256>/`.
The full packet digest is in the receipt; one hash directory keeps Windows
checkout paths short. Identical verified reseals reuse the existing receipt.
It contains the exact source ZIP, unchanged extracted packet, retrieved manifest,
archived metadata and three frames when fully verified, plus `receipt.json`.
Partial burst retrieval is not represented as complete retention. Source failures
are retained under `source-gaps/<receipt-sha256>/`; missing, expired, corrupt or
failed readback is EVIDENCE_GAP and the biological/whole-morning outcome remains
UNKNOWN. The readback function reopens the inventory and all hashes and rechecks
the original packet. Keep the pinned receipt SHA when auditing later reads.
These are content-addressed, create-only application receipts; Git history is
the durable provenance path, not an infrastructure-level WORM guarantee.

`matched_control_sealing.yml` runs only on explicitly named research sealing
branches when code/selection changes; it has no cron and changes no capture
schedule. It reads the selection in `research/matched_control_selection.json`,
seals it, commits only the research archive to that same branch (never main),
fetches the remote commit and reopens every committed evidence byte for readback.
Review/merge the archive PR before deleting its branch. Durable Git evidence does
not expire with the source Actions artifact; normal repository backup/retention
still applies. No credentials or signed download URLs are stored. Existing
owner-authorized Montrose media publication policy applies.

Example (GH_TOKEN grants Actions read; the R2 endpoint is public):

```sh
python model_data/seal_matched_control_packet.py \\
  --artifact-id 11273358871 --run-id 37123527771 \\
  --source-commit 6563e4682b2c9381a6407e8dd120e00b59146108 \\
  --r2-public-base https://pub-bf6207fce382460991eaf48ec8090b1a.r2.dev \\
  --archive-root research/matched_control_archive
```

Selecting this first post-merge packet is an archival integration test, not an
outcome-conditioned control sample. Its scoped candidate label, unresolved
pairing, UNKNOWN intervals/morning, zero training negatives and Tier-A false
are preserved. Tests cover missing/expired artifacts, failed GETs, corrupt or
missing frames, identity/timing/hash mismatches, manifest instability and failed
durable readback. Production probabilities, weights, thresholds, alerts,
forecasts, event labels and schedules are unchanged.

Verified integration: artifact `11273358871` ZIP SHA-256
`345ea4f64966c5d2c7381ebfec926dd0cf06ce01ef5f3e06b4024f90c6b3a80a`
was recovered and all retained bytes verified. R2 capture ID
`20261003T072614360169-2a6c43079065` matched the 07:26:14 CDT source packet;
three shoreline frame hashes and capture/shot metadata passed. Sealing run
`37131230734` committed the complete evidence and reopened the remote Git
bytes successfully. Packet SHA-256 is
`402794882f85e2bcb48b1f5c8cf20d8f3c55c4351087478deb9748cc207bca4d`;
receipt SHA-256 is
`e634fdfd50a75dd358fc86e745a57fe18e856e9b749959bfd809b0b067fb697d`.
The earlier failed authenticated artifact GET remains as its immutable source-gap
receipt; the independent public GET recovery resolved that retrieval without
weakening hash validation. Neither archive receipt assigns a biological label.

## Event-side comparator follow-up — October 3

See `MONTROSE_EVENT_COMPARATOR_20261003.md` for recovered August 29 media,
the precise unresolved 437 geometry/time binding, and the separate frozen
matching protocol. Eleven recovered media files were hashed; one has a genuine
offset-aware capture time and GPS, but none establishes the exact comparator.
The retained October 3 pixels also require physical geometry and contact-class
detectability review despite verified archive integrity. No pair was scored.
`collect_event_comparator.py` now extends the same outcome-blind research
workflow with immediate verified three-frame GET retention, protocol bytes/hash
and an empty event-review ledger. Selected packets still use the existing PR52
durable sealer. This is a research collection change, not Tier-A admission.

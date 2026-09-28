# Contact-sheet feasibility test — September 27, 2026 CDT

Decision: research only. Do not deploy or connect to the production analyzer.

## What was tested

Inspected main's analyzer at tree 3bdf7e891c9e0f2c2fec0c98a1032f29c6cfe19d.
It already sends three images in ONE request per camera. Combining them offers
zero request-count savings. No actual token, price, or inference-latency savings
have been demonstrated.

Added a standalone, opt-in, in-memory lossless PNG contact-sheet builder.
It preserves all decoded source pixels (including tiny points and edge pixels),
keeps chronological frame numbers and timestamp provenance, and uses one camera
per composite. It rejects missing frames, ambiguous ordering/timestamps, mixed
camera identifiers, mixed dimensions, corrupt media, unsupported orientation,
and excessive pixel dimensions. It never downloads or saves media, calls a model,
publishes observations, or changes schedules, forecasts, alerts, or live code.

Validation: 10 new tests plus 9 existing vision-efficiency tests passed (19 total).
The existing suite uses a mocked model client; these are NOT inference tests.
Synthetic 640x360, 1280x720, and 1920x1080 three-frame fixtures also passed exact
decoded RGB round-trip comparison. Timings and byte counts are recorded in
contact_sheet_offline_results_20260927.json. Their simple artificial imagery
compresses well and must NOT be used to estimate real camera savings. Pixels
preserved in a file do not establish that a model processes them at equal detail.

## Reproduce offline

Requires Python and Pillow. From repository root:

    python -m unittest discover -s tests -p 'test_contact_sheet_probe.py' -v

For an owner-camera burst, prepare a manifest with camera_id and three shots;
each shot has file (relative path), shot (1..3), timestamp_ct (timezone-aware),
and timing (actual/nominal provenance). Then:

    python research/contact_sheet_probe.py /path/to/manifest.json --report /path/to/research_metrics.json

Only the report is written; image payloads stay in memory. Public-camera media
must remain transient and cannot be archived as a research dataset. Never use
production vision.json or any live status path as the report destination.

## Remaining validation before any promotion

The accessible repository has latest individual camera images and burst metadata,
but does not expose the complete three-image bursts used by the desktop analyzer.
No desktop access or model API execution was established for this experiment.
Consequently NO paired live-model comparison was run, and detection equivalence,
model latency, and token cost remain unmeasured.

Next use an isolated replay of complete authorized owner-camera bursts, including
daylight, dawn/darkness, glare/wakes, small biological features, people/flashlights,
and safety-relevant examples. Preserve originals and run the existing three-image
request and the candidate against the same model, rubric, output limits and
timing metadata. Candidate instructions must explicitly explain row-major panel
order, blank padding, and panel-relative locations. Do not feed results to alerts.
Record actual usage, wall-clock latency, failures, and per-field disagreements.
Counterbalance order/repeat a subset to distinguish stochastic variation.
Have disagreements reviewed against source frames; agreement alone is not truth.
Absence of positive examples is not proof of retained event sensitivity.

Do not promote until a representative paired trial shows a material measured
benefit with no observed loss of important biological/safety evidence and no
unknown-to-absence regressions. A finite test cannot establish zero risk.
If benefit is negligible or evidence remains insufficient, retain separate images
in the existing single request. No automatic rollout is configured.

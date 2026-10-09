# Meaher / NGOFS2 research integration correction — 2026-10-09

- Corrected normalized NGOFS2 input mapping to evidence_class, vertical_role and value. Output schema remains compatible.
- Preserved 180-minute valid-time freshness; actual retained October 7 bottom-current row remains UNKNOWN_STALE_MODEL_TRANSPORT at October 9 08:30 UTC (age 2,850 minutes), with null interaction.
- Enforced ARCOS availability at issue time for latest values, time windows and issue-time DO admission. Default issue time is generation time, so recently retrieved historical observations are not falsely labeled as available at their original observation time.
- Actions sensing run 37920243743 (2026-10-09 10:52 UTC) attempted newer NGOFS2 datasets. All products reported NetCDF DAP server errors. Point Clear wrapped/truncated its errors; availability validation rejected that RuntimeError and withheld NGOFS2 publication, leaving the October 7 retained manifest.
- Point Clear now retains structured individual retrieval attempts. Availability recognizes only nonempty sets of confirmed NC_EDAPSVC errors; mixed/parser/schema failures stay fatal. No schedules changed. This repairs reporting/publication of unavailable guidance; it does not establish NOAA recovery.
- Focused offline verification: 30 tests on PointClearPC in an isolated Documents/Codex directory; no live capture runtime changed, no paid model calls.
- Fixture contains one exact retained normalized bottom-shoreward row plus the actual CSV header. Tests cover fresh signed/zero values, stale and boundary ages, missing/nonfinite values, future valid/availability times, malformed times, ARCOS issue-time exclusion, null interaction, and collector failure serialization/classification.
- Production weights remain zero. No changes to probabilities, thresholds, camera coverage, schedules, 21:00 notification policy or alert behavior. Predictive validity remains NOT_ESTABLISHED; Meaher is upper-bay oxygen evidence, not direct Point Clear bottom oxygen or a validated Jubilee precursor.

Collector evidence: https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37920243743

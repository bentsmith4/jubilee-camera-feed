# Water-quality findings — corrected September 6, 2026

**Current conclusion: INSUFFICIENT_VALIDATION. No production-weight change.**

This replaces the September 5 interpretation that bacteria probably provides little predictive value. The original file and outputs remain available in Git history. That interpretation was stronger than the underlying exploratory comparison supported.

The first comparison included event-day samples, counted repeated lag memberships as an aggregate observation count, lacked explicit station/event matching, and treated dates without known reports as comparison controls without verifying observation effort. Those shortcomings prevent a valid finding either for or against predictive utility.

The corrected implementation:
- excludes all samples on the event date when exact forecast/availability timing is unresolved;
- preserves censoring, source status, station/method IDs, units, depth and unknown publication timing;
- reports unique observations separately from overlapping lag memberships;
- requires explicit station mappings for geographic comparisons;
- labels background observations as unlabelled, not verified non-events;
- never promotes a variable from this exploratory diagnostic.

See `water_quality_ingest_manifest.json`, `water_quality_backtest.json` and `water_quality_run_summary.json` for the dated executed results, and `science_and_validation_review_20260906.md` for the revised research priorities. Ingested rows establish accessible data, not forecast skill. Mobile Baykeeper PDF sources are still references unless an ingest manifest explicitly records their parsed rows.

Enterococcus remains a research-only microbiological/runoff proxy, never a replacement for dissolved oxygen. Magnolia River oxygen/salinity records remain geographically explicit regional observations, not direct Eastern Shore bottom conditions.

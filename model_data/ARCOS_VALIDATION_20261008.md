# ARCOS validation — October 8, 2026

PR #77 merged externally at 726889344b3526851a84b5df22332878be94b556 while this validation was in progress. Follow-up repairs are necessary for complete current-state admission and publication triggering.

## Public observations

- Independent live collector completed at 22:27:15 UTC: 1,066 normalized measurements, five hydrographic stations, eight meteorological stations. Bon Secour, Battleship Park and Gulf State Park hydrography was empty; Middle Bay hydrography and meteorology were empty. Dauphin Island latest samples were stale and were admitted as UNKNOWN, never zero.
- Exact gzip responses were decompressed and SHA-256 verified; reparsed rows matched normalized CSV semantically. Live current-state rebuild passed the binding/freshness checks. All ARCOS rows retain zero production weight and direct local bottom identity remains false.
- Separate Meaher 24-hour source response independently confirms approximately 0.23 mg/L and 3.10% saturation at 2026-10-08 11:30 UTC / 06:30 CDT. The response and hash are retained in arcos_validation_20261008. This is upper-Bay station evidence, not Montrose or Point Clear bottom oxygen or a Jubilee event label.
- Original merged collector run https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37853450852 succeeded. Its first execution was a push event, not proof of subsequent cron execution.

## Corrections

- Verify both empty and populated stream archives and support legacy station manifests.
- Preserve actual per-stream retrieval timestamps and bound network retry budget within the 12-minute job timeout.
- Select latest observations by parameter; explicitly retain missing hydrographic parameters as UNKNOWN when only weather is available. Include ARCOS admission state in reconciliation identity so elapsed freshness can trigger a new snapshot.
- On total outage, clear old normalized rows and declare unavailable, permitting UNKNOWN publication.
- Add ARCOS workflow completion to the existing current-state workflow_run producer list because bot pushes do not trigger downstream push workflows. Separate PR collector concurrency from main collection; run offline tests outside the operating season too.
- Preserve probabilities, alert gates, thresholds, camera cadence, Weeks Bay ingestion and all zero weights. No paid model calls or PointClearPC writes.

## Regression evidence

10 focused parser/collector tests; 24 ARCOS integration and inherited reconciliation tests; 24 freshness tests; 15 desktop acceptance tests; 3 Weeks Bay tests passed. The integration fixtures verify missing, stale, QC-rejected and corrupt-archive cases, bound forecast outlooks and gates, and zero weights. A total outage test verifies stale CSV clearing. YAML syntax is valid. Current-state live admission was KNOWN for fresh valid station measurements, UNKNOWN_STALE for Dauphin Island, and UNKNOWN for missing stations/parameters.

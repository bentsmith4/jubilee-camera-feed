# Material-input fault recovery assessment — October 5, 2026

## Scope and original fault

This is an explicit operational assessment of the existing material-input latch. It is not a new Jubilee prediction, scientific calibration, desktop/archive acceptance or authorization to fill missing inputs.

The current uninterrupted latch began at [1d1f4c7](https://github.com/bentsmith4/jubilee-camera-feed/commit/1d1f4c7f4472a8da81b22580f2faa889eed7ab83), October 1 at **03:54:17 CDT**. Its recorded basis was simultaneous loss of all six fresh owner-camera views, KBFM/KMOB regional weather and every lower-river series. The successful camera captures had aged to 105–108 minutes against a 60-minute limit; this was freshness loss, not six capture failures. [c1e54bd](https://github.com/bentsmith4/jubilee-camera-feed/commit/c1e54bd941a10ac3d43e02eb5b45a6a3016d36ae) reassessed the same degradation on October 2 at 04:04:12 CDT. Subsequent reconciliation preserves that assessed gate; it does not count UNKNOWN fields to infer recovery.

The preceding explicit recovery, [dce0a6b](https://github.com/bentsmith4/jubilee-camera-feed/commit/dce0a6bf20989555c72fa09cc62df732486c5a84), October 1 at **02:20:43 CDT**, cleared the material fault with six fresh matching camera bursts and current regional ASOS/river context. It explicitly retained poor nighttime detectability, stale Weeks Bay context, blank rain and missing local bottom/oxygen observations. Named-station forecast **and shoreline grid** were SOURCE_UNAVAILABLE/UNKNOWN in that cleared snapshot. Thus neither all scientific measurements nor all NGOFS2 slices were established prerequisites for clearing this acute fault.

## Materiality of the remaining gaps

| Class | Evidence and determination | Effect on this recovery |
|---|---|---|
| Original operational freshness loss | Six camera views, the two airport stations and qualified lower-river context are reevaluated against their unchanged issue-time limits. PR #63 fixed the demonstrated acquisition scheduling gap. | Requires current accepted evidence plus repeated successful refreshes. No clearance from historical retrieval success alone. |
| NGOFS2 acquisition outages | Point Clear forecast and named-station nowcast/forecast report `NetCDF: DAP server error`. These are real acquisition failures, not absent scientific instruments. Point Clear nowcast supplies antecedent model context only; shoreline grid supplies only its published cells, depths and sampled valid times. | Degraded zero-weight model context, not an independently demonstrated material fault for this frozen heuristic assessment. All unavailable slices and missing transport windows remain UNKNOWN; no substitute observed-current claim, interpolation or old-CSV fallback is admitted. |
| Scientific/design limitations | Direct local bottom/contact-strip DO, salinity/temperature and stratification; local observed currents/water level and shoreline weather; calibrated river-to-Bay lag; and unobserved biological outcomes remain UNKNOWN. | Limit confidence and scientific validity, but do not by themselves sustain the original acute operational latch. They were present in the preceding cleared state. No claim of improved predictive skill. |
| Separate verification limitations | Current all-six desktop/archive acceptance remains NOT_VERIFIED. Metadata health does not establish archive acceptance, beach/contact-strip coverage or a non-event. | Preserve the separate verification status. It is not evidence of an active capture failure or an excuse to claim acceptance. |

Zero production weight alone does not make an outage harmless. Here the materiality determination also rests on the original fault's recorded scope, the earlier recovery precedent, the retained UNKNOWN coverage and the absence of any newly calculated probability or claim requiring the missing model slices. A future assessment relying on those slices, a source conflict, a parser/provenance failure or a new camera/weather/river loss requires its own materiality review. The older whole-process NGOFS2 timeout remains `UNRESOLVED_PROVIDER_OR_CLIENT`; today's DAP errors do not retrospectively resolve it.

## Repeated main-branch recovery evidence

| Accepted snapshot | Main commit | ASOS retrieval / river retrieval (UTC) | Camera ages at issue | ASOS wind ages KBFM / KMOB | Qualified fresh river series |
|---|---|---|---|---|---|
| Oct 5 11:19:05 CDT | `cd823a545f` | 16:17:18 / 16:17:23 | 9.824–12.568 min | 26.094 / 23.094 min | 20/20; 49.094–79.094 min |
| Oct 5 12:14:59 CDT | `77297c6d46` | 17:11:39 / 17:11:41 | 5.672–8.404 min | 21.997 / 18.997 min | 20/20; 44.997–74.997 min |
| Oct 5 13:15:04 CDT | `3e06c7049f` | 18:12:06 / 18:12:07 | 5.868–8.579 min | 22.076 / 19.076 min | 20/20; 45.076–75.076 min |

The first [refresh run 37339569722](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37339569722) followed the workflow change. Subsequent [run 37346512231](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37346512231) and [run 37353984227](https://github.com/bentsmith4/jubilee-camera-feed/actions/runs/37353984227) were successful `push` runs on camera-publication commits `d17a99e13fd166bce21dc316af32e6a30dacdf3f` and `dda2dac59977bb682a11fada06f2da14b4688bd6`. They establish that the new event path executed twice and produced repeated fresh admissions; they do not guarantee future scheduling or continuous freshness between publications.

## Explicit recovery criteria

1. Read one committed evidence generation and validate provenance, archive readback, per-source admission and exact state/forecast binding using the existing code. No dirty, failed-producer or uncommitted evidence qualifies.
2. Require six healthy matching camera views no older than 60 minutes, current QC-admitted regional wind context from both KBFM and KMOB under the 90-minute rule, and qualified lower-river context under the 180-minute rule. For this assessment, retain the demonstrated 20/20 series coverage. Missing optional parameters stay UNKNOWN.
3. Require repeated successful post-PR #63 refresh/admission cycles, including the camera-triggered path. The table above satisfies this bounded retrospective requirement.
4. Review the residual outages and scientific/verification gaps explicitly, as above. No new material conflict, capture failure or positive event may be silently cleared. Preserve the strict four-trigger notification OR; recovery is operational context, not a fifth trigger.
5. Recheck current source ages and main before publishing. An accepted 13:15 snapshot is not indefinitely fresh. If the criteria no longer hold, preserve the latch and record the actual blocker; do not backdate clearance or relax age limits.

## Publication-time check

An intermediate replay of main `3e06c7049fa23ab2662d919db8b0e7d52705826a` at **14:08:27 CDT** found four views aged beyond 60 minutes (Montrose boat 61.961, Montrose shoreline 60.331, Point Clear E2 back deck 61.318, Point Clear E2 bay mouth 60.826). Montrose bird and Point Clear E3 were still within the limit. Weather and all 20 river series remained admitted. No clearance was published from that replay. The final decision below uses the last explicitly checked evidence and clock.

## Preserved boundaries

Probability ranges, central estimates, dates, confidence, zero production weights, the strict `>20%` comparator, source-age limits, UNKNOWN semantics, producer gates, camera cadence and the existing 9 PM gate are unchanged. No event/absence claim or forecast notification is sent by this assessment. The `active_faults` array historically duplicates scientific `known_unknowns`; its presence alone is not the material alert criterion.

## Final assessed result

**Recovery accepted.** The original material fault and forecast notification condition are cleared; notification suppression is true. Recovery remains operational context only.

Assessment clock and committed evidence:

```json
{
  "issue_time": "2026-10-05T14:17:45.649782-05:00",
  "assessment_time_utc": "2026-10-05T19:19:07.471282+00:00",
  "reviewed_main_commit_sha": "e1cc8200a0afd03d69b7de8f085daf08fd294875",
  "input_commit_sha": "3faef9d15bb9cbeaaf90869e855aa49184d47180",
  "decision": "RECOVERED_ORIGINAL_OPERATIONAL_FRESHNESS_FAULT",
  "camera_ages_minutes_at_review": {
    "montrose_pier_boat": 12.095,
    "montrose_pier_bird": 9.268,
    "montrose_shoreline": 10.373,
    "pcl_e2_back_deck": 11.375,
    "pcl_e2_bay_mouth": 10.865,
    "pcl_e3_bay_mouth": 9.73
  },
  "asos_wind_ages_minutes_at_review": {
    "KBFM": 26.125,
    "KMOB": 16.125
  },
  "fresh_river_series": 20,
  "river_age_range_minutes_at_review": [
    49.125,
    79.125
  ],
  "alert_gates": {
    "point_clear_over_20_percent": false,
    "daphne_may_day_over_20_percent": false,
    "direct_event_evidence_present": false,
    "material_critical_input_fault": false,
    "notification_suppressed": true
  },
  "notification_condition_met": false,
  "blockers": [],
  "snapshot_sha256": "d01176d4038cee8bffa0f151080831e5a10b012a0ab7968cdd751e451012de97"
}
```

The state and forecast are committed together. The binding check verifies exact snapshot bytes, issue time, evidence commit, unchanged outlooks and the four-trigger notification contract. Existing source replay validated the committed raw/normalized evidence, retaining unavailable model slices as UNKNOWN. No executable code, source manifest, sensing schedule or publication gate is changed.

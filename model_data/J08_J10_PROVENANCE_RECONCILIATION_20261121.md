# J08/J10 provenance reconciliation — 2026-11-21

This receipt records the bounded provenance and source-disposition corrections authorized for the existing Research lane. It creates no event label, matched negative, model feature, production weight, alert, schedule, acquisition, outreach, or spending authority.

## Biological-label corrections

### NOAA 2011 classroom exercise

Source: NOAA, *The Jubilee Phenomenon Teacher Guide*, page 21, Bon Secour station exercise.

- June 25 is retained only as a **source-reported positive lead**. The classroom answer key is not independent biological confirmation and is not a fit receipt.
- August 5 and August 25 are **environmental examples with unknown shoreline biology**, not validated positives or negatives.
- August 5 is not a tide-only contrast: the answer key also reports that wind did not turn easterly until about 9 a.m., well after dawn.
- The Fairhope report cluster is not assignable to August 25 from this exercise.
- All three dates remain zero-weight. A bounded audit already found no persisted biological-label use, so no audit or model rerun is warranted unless new evidence demonstrates actual downstream use.

### September 1950 reported false alarm

Source: *The Mobile Press*, September 19, 1950, page 2, “Jubilee Cry False Alarm”; existing visually verified Mobile Public Library scan.

- The Monday-night September 18 call brought scores of people with lights and equipment to the Daphne/Eastern Shore beach, with activity continuing past midnight.
- The report yielded a few scattered crabs and called the episode a false alarm.
- Keep this episode distinct from the successful September 17 catch.
- Disposition: documented search effort, but **not a clean negative** and not proof of biological absence. Exact shoreline segment, interval, coverage and detection conditions remain unresolved.

### Fisheries-mortality leads

- **July 19, 1982 — Bon Secour Bay:** Gulf States Marine Fisheries Commission annual report 33 reports 20,000 eels and 12 flounder dead, with provisional Jubilee attribution. Time, live shoreward behavior and mortality footprint are absent. Retain as mortality evidence only.
- **July 22, 1982 — Bon Secour River:** NOAA CAGES station 28, tow/sample 837 reports dissolved oxygen 2.8 mg/L, temperature 29.0 °C and salinity 16.0 PSU. The reading is three calendar days later; sample hour, depth and spatial relationship to the mortality are unverified. Retain as nearby river background only, never event oxygen or calibration evidence.
- **Fiscal year 1993 — Eastern Shore:** GSMFC annual report 44 reports an Eastern Shore mortality exceeding 1,000 fish associated with a Jubilee, without a date or specific shoreline. Keep at fiscal-year precision and distinct from its separately reported low-oxygen menhaden kill.
- **August 31, 2011 — Fairhope Yacht Club:** Storm2K post 2187650 establishes intentional local-evening search effort inferred from the dated post. Exact window, footprint and biological outcome remain UNKNOWN. Do not use as a negative or date an event from it.
- A single bounded July 19–31, 1982 Baldwin County newspaper check remains optional only through already-authorized accessible digitized holdings. A holdings list is not evidence that scans are available. Park absent corroboration; no outreach or paid access.

## Completed offline sensitivity evidence

### Bon Secour ambient cadence replay

Source: BCO-DMO dataset 941205, three original ambient files; publisher hashes matched.

- Valid two-minute-grid readings: 741, 728 and 748.
- Worst-case point-sample minimum inflation across integer clock phases:
  - nominal 5 minutes: 0.05 / 0.02 / 0.04 mg/L; minimum-time shifts up to 4 / 2 / 4 minutes;
  - nominal 15 minutes: 0.16 / 0.10 / 0.07 mg/L; minimum-time shifts up to 40 / 12 / 80 minutes.
- Fixed-bin averaging was evaluated separately. Both methods retained the broad first-file overnight low, but neither establishes fidelity to the published transient.
- Raw and merged deployment-1 clocks indicate August 5–6, 2021 while the paper describes August 7–8. No clock correction or external join is inferred.
- Disposition: site/trace sensitivity only. This is not a Jubilee threshold, event label, cadence decision, or reason to rerun the replay by default.

## External timing/rules comparator

### Alabama Fishing Atlas Jubilee Watch

The public checklist uses a fixed Point Clear pre-dawn window of 02:00–06:00 Central and five rules. It explicitly says it is a checklist, not a forecast, and notes that it lacks an open live Eastern Shore bottom-oxygen feed.

- Reuse the frozen PR #91 timing inventory; do not create a competing model.
- Compare the documented 1947 Point Clear, 1950 Daphne and 2020 Fairhope positives against the fixed window while preserving geography and unknown onset.
- A documented event outside the window is a rule/window exclusion, not proof that the full checklist “missed” when issue-time inputs are incomplete.
- Positive-only cases can test coverage and rule exclusions. They cannot estimate false alarms or comparative discrimination.
- Missing issue-time values remain explicit. A retrospective-observation variant must be labeled separately. Social silence is never a negative; the existing matched-control contract controls.

## Release-gated regional sources

- **Mississippi Bight summer 2025 hypoxia:** Gulf Conference 2026 abstract reports long-term mooring and survey evidence of intermittent/widespread shelf hypoxia and transport/mixing dependence. Retain as regional, abstract-only context until data and deployment metadata are public. It is not a Jubilee label or Eastern Shore oxygen proxy.
- **Coastal Alabama baseline campaign:** Fletcher, LaBon and Lehrter report monthly surface/bottom water and sediment sampling beginning September 2025 across Mississippi Sound, Mobile Delta, Weeks Bay and surrounding rivers. Retain as a release-gated regional lead. Reopen only when a public data deposit or station inventory exposes verified fields, depth, timestamps and QA.
- Middle Bay Lighthouse remains already tracked and offline. Reopen only upon verified timestamped live observations with depth.

## Wake and Fly Creek leads

- The Fowl River study (DOI 10.1007/s12237-026-01813-3) is an optional pressure-gauge/wake-methods reference. Its monthly oxygen observations do not demonstrate a synchronized oxygen response or an Eastern Shore effect.
- David Rainer’s undated Fairhope-area account supports only a hypothesis that a ship wake altered visible Jubilee behavior. It does not establish oxygen mixing. The 2023 account repeats the same episode and is not an independent witness.
- July 17 and July 24, 2025 are only clip-search anchors. July 17 is indexed as a photo report; the July 24 WKRG item has morning-level timing, and its 10:42 a.m. Central publication time is not filming time. No repeat search is needed.
- No other retained clock-verified continuous shoreline clip spanning an observed wake was identified in this checkpoint. Park the comparison without AIS download. AIS alone could identify a possible transit but not local wake arrival.
- John Borom’s Fly Creek account and reported dolphin video establish June and dawn context but no year or day. Keep it separate from the June 22, 2022 UF/IFAS article unless original evidence links them; no event label or model use.

## Current integration gates

- PR #171 remains draft/unmerged at `a22f6bfc6b761e5b37d6e6e264faa1bcaebee0eb`. The external-observation adoption test and existing owner acceptance remain unresolved; no duplicate repair is authorized.
- PR #187 remains draft/unmerged at `058e26248c403f8f8587d497296bb6df6b92143e` with exact-head Research preservation PASS and green hosted checks. The separately attributable Sensing operational-owner decision is still missing, so the shared fixture correction has not reached main.
- The November 17 scheduled WQP run therefore remains failed-before-ingestion. The next nominal natural slot is November 24 at 05:17 Central; acceptance requires actual ingestion/publication plus manifest, coverage, archive hash and append-only-history readback. No manual dispatch.

## Durable disposition

The two observation-effort episodes are added to `historical_human_control_candidates.json` without creating clean negatives. The source and method leads are added to `historical_event_source_registry.json` with zero-weight/release-gated guardrails. Duplicate discovery checks are retired. Reopen only on the evidence triggers stated above.

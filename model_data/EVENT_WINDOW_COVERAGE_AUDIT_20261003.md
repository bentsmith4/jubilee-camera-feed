# Afternoon, evening and cross-midnight evidence audit

Research only. Audited current main `6287202bc40dd1a0f8aa7a93a8dcdad1cf834782` after PR #56 (`defbc99ab65376d7c2b991e735f349aac24f9f9c`). No production settings, camera cadence, probabilities, alerts, thresholds or 9 PM feedback gate are changed. No new negative or Tier-A label is admitted.

## What the recovered reports require us to test

Source: `loesch_newspaper_scan_evidence_20261003.json`, inspected original Mobile Press pages recorded by PR #56. Historical local time standard remains UNKNOWN; these are analogues in today's America/Chicago clock, not historical UTC conversions or exact modern ROI matches.

| Report | Modern observable path | Remaining limits |
| --- | --- | --- |
| June 14, 1947 Point Clear: late afternoon, underway about dark, Saturday night | In-season hourly canonical bursts at :06 through 19:06, then 20:06 and 22:06; live latest-image feed between cycles | Late afternoon has no precise start. Point Clear cameras lack a close beach/swash-zone view; twilight/night detectability and exact historical location binding are unverified. |
| August 5–6, 1950 north Montrose: about 19:30, catch by 03:00, Sunday daytime crabs | 20:06, 22:06, next-day 00:06, 02:06 canonical baselines; dawn +/-2 hours overrides baseline with 20-minute slots; subsequent daytime hourly | A 19:30 onset can precede the next canonical burst by ~36 minutes; two-hour gaps can miss shorter phases. The corridor is not bound to the 437 ROI. The 03:00 catch is not a verified biological end; Sunday continuation needs separate evidence. |
| September 17, 1950 Daphne: about 17:30 to midnight | 18:06, 19:06, 20:06, 22:06; next 00:06 lies beyond midnight | Sparse bursts do not prove continuous coverage. Daphne locations outside the six views remain unobserved; no whole-corridor negative follows. |

Schedule basis: `desktop_runtime/capture_service.py`, not legacy `scheduler_router.py` or older README descriptions. Canonical capture is seasonal May 18–November 14 (`seasonal_policy.py`). A 15-minute global floor, serialized processing and retries can shift actual times; slots are intentions, not proof of successful captures. Adaptive acceleration is pre-dawn only. Historical dates fall inside the seasonal window; off-season canonical monitoring is paused.

## Evidence retention and non-event logic

- Canonical `upload_frames.py` freezes a local capture, uploads timestamped R2 burst frames and metadata, reads hashes back, and advances the latest pointer last. This is the implemented path, not a verified inventory of today's remote archive. Lifecycle status remains unverified in `data_retention_policy.json`; proposed 3-day live and 90-day canonical retention are not applied promises.
- The live loop targets a 180-second refresh **after serialized work**. `live_upload.py` replaces `live/<camera>.jpg` and status; no implemented immutable live buffer is shown. Seeing an image live does not establish retrievable historical coverage. Canonical work can delay live refresh.
- The public Git mirror retains the latest frame per camera; Git history is not the full three-frame archive. Selected matched-control sealing can preserve verified packets, but it is not automatic preservation of every afternoon/night/event window. Restore one current, prior-day and prior-week canonical manifest plus all expected images before claiming archive availability.
- `append_if_target_window` writes a dawn-only legacy ledger, but the active `observation_logging.yml` calls `publish_observation_record.py`, which already stores immutable records for all captured clock windows. It runs on camera-state pushes and hourly at :17. Checkout-time latest state and workflow queuing can miss intervening captures; metadata count is not a completeness guarantee or independent pixel review.
- Existing controls are already conservative: dawn candidates are visible-scope only, Point Clear lacks a primary contact view, no-report is not negative, and `collect_matched_control_packet.py` explicitly keeps between-burst intervals and whole-morning outcomes UNKNOWN. The risk is downstream reuse of a scoped morning label as a whole-day negative, or treating schedule/live availability as retained, detectable observation. The new audit explicitly forbids both. Dawn-only matching criteria cannot validate evening positives; no tolerance or training scope is broadened here.

## Smallest implemented validation

`audit_event_window_coverage.py` reads existing immutable observation records and writes an exclusive-create research receipt. It joins across midnight, deduplicates equivalent instants, rejects contradictory identities and naive timestamps, excludes future records, and measures maximum elapsed gaps between usable **upstream effort samples**, including window edges. A usable sample requires explicit successful capture, empty integrity issues, good/fair visibility and moderate/high detectability. It neither reads remote media nor infers continuous observation, event absence, independent camera sites, or exact historical ROI correspondence. Missing media readback remains UNKNOWN even when effort looks usable.

Screening windows (overlapping deliberately to address different source reports): 15:00–20:00 as an exploratory late-afternoon bracket; 17:30–24:00; 19:30–next 03:00; and next 03:00–12:00 as an exploratory continuation bracket. These bounds are not historical precision, a measured event duration or an exhaustive coverage window. The midnight-crossing sequence and next-day period remain linked to the original date rather than being counted as independent events.

Pinned receipt `event_window_coverage_20261002.json`: 763 input records hashed, cutoff October 3 at 18:06:32 CDT; completed October 2/3 windows.

| Modern screening window | Retained effort records | Usable montrose_shoreline samples | Maximum elapsed unsampled gap for montrose_shoreline |
| --- | ---: | ---: | ---: |
| 15:00–20:00 | 5 | 4 | 114.0 min |
| 17:30–24:00 | 4 | 1 | 354.0 min |
| 19:30–next 03:00 | 4 | 0 | 450.0 min |
| Next 03:00–12:00 | 17 | 10 | 205.5 min |

All six cameras have zero usable upstream biological effort samples in the 19:30–03:00 window. This is a detectability gap, not evidence that events occurred or did not occur. It does not establish independent media readback or all-cycle retention. October 3 has afternoon records through 18:06, but tonight's later windows were not elapsed at the pinned cutoff; do not mark them missing or negative in advance.

Reproduce on a pinned checkout, writing a NEW receipt outside the checkout:

```sh
python model_data/audit_event_window_coverage.py --date 2026-10-02 --as-of 2026-10-03T18:06:32-05:00 --out /tmp/new-event-window-receipt.json
python -m unittest discover -s tests -p test_event_window_coverage.py -v
```

Next research acceptance: rerun after a completed modern evening/cross-midnight window using existing records; verify associated canonical R2 manifests, all three frames, timestamps and hashes across both dates using the existing archive readback/sealing path. Preserve failed and poor-view samples. Independently review twilight/night pixels for the precise visible shoreline before calling a sample biologically usable. Do not collect new private imagery into public Git. If those checks still show insufficient detectability, bring a specific sensor/illumination/retention proposal with evidence; this audit does not authorize a production change.

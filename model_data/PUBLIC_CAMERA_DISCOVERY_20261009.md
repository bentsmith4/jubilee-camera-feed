# Public-camera discovery review — October 9, 2026

Status: DISCOVERY_REVIEWED; new camera live acceptance NOT_VERIFIED. No new camera admitted to production.

## Scope and evidence
Ben supplied the AL.com camera roundup:
https://www.al.com/news/mobile/2026/10/watch-live-beach-cams-as-hurricane-isaiah-landfall-looms.html
The article was recovered using a live Firecrawl text fetch after the web reader failed. Camera pages and public search were checked; no third-party media was retained. Text/player errors below describe this client check, not a proven global camera outage.

Existing contracts were read from model_data/public_camera_signal_contracts.json (blob 9fed034b54f3b9ba187d24cb9169f33753896995). Fairhope Pier and Grand Hotel already have contracts. This report does not modify those contracts, observations, model weights, probabilities, alerts or schedules.

## Article candidates
| Source | Proposed role | Disposition |
| --- | --- | --- |
| Fairhope municipal pier https://www.fairhopeal.gov/visiting/piercam ; current embed https://www.youtube.com/watch?v=N5wWOVOTHmQ | Existing pier activity/environment proxy | Operator page confirms same YouTube link as article. Contract says adjacent north/south beaches are not visible. No beach-wide negative. Embedded-page browser attempt timed out. Direct YouTube recovery succeeded: paused=false, readyState=4, live badge class ytp-live-badge-is-livehead; playback values 46804.139324, 46809.550595, 46811.764475 seconds (7.625151-second advance). Exact wall-clock sample interval and actual scene progression were not established; playback metadata verified, full visual admission remains NOT_VERIFIED. No biological observation made. |
| Beach Club https://www.youtube.com/watch?v=l2em7gqBj00 | Regional Gulf weather context only | Article describes southward Gulf-facing view on Fort Morgan peninsula. Not a Mobile Bay shoreline observation; individual playback not validated. |
| Turquoise Place https://www.youtube.com/watch?v=pJqrjIuvGFE | Regional Gulf weather context only | Article describes southeast view at Orange Beach. Low Jubilee priority; individual playback not validated. |
| PerdidoKeyOG https://www.youtube.com/watch?v=qVzKF34qUYg | Regional Gulf weather context only | Outside target shoreline; individual playback not validated. |
| HD Beach Cams https://www.youtube.com/watch?v=t6FtD06yy44 and Surfers View https://www.youtube.com/live/HCcubKg_giA | Discovery directories/rotating regional views | Every segment needs location and observation interval; not a continuous fixed-site observation. Deduplicate underlying feeds. |
| FAA Dauphin Island https://weathercams.faa.gov/map/-90.69072,26.94351,-69.64092,41.96921/cameraSite/875/details/camera/13208 | Candidate bay-mouth visibility/weather context | FAA app shell loaded; actual camera frame, bearing and capture timestamp not verified. Page clock is not image time. |
| Santa Rosa Island Authority/Pensacola views and Florida Traffic https://www.youtube.com/watch?v=74tGZEkFiB4 | Outside target | Not Eastern Shore Jubilee evidence. |

Coastal Camera Network https://coastalcameranetwork.com/ was inspected as a further discovery route. It describes a hosting platform, not proof of additional Mobile Bay camera coverage. Do not count platform/mirror URLs as independent cameras.

## Additional Mobile Bay leads
| Lead and source | Evidence from review | Decision |
| --- | --- | --- |
| Grand Hotel / Point Clear https://hazcams.com/station/point-clear-al-us-001 | Existing contract. Page returned player error, N/A position/buffer, station latency not measured. | Existing environmental/activity proxy; live freshness UNKNOWN for this check. Ambiguous Update Timestamp must not be interpreted as image age. |
| Daphne / D'Olive Bay, Hampton Inn https://www.webcamtaxi.com/en/usa/alabama/mobile-bay-delta-cam.html | Page identifies hotel and broad bay/I-10 view but labels webcam temporarily offline. | Highest-priority additional northern-bay lead; site label is not proof all source routes are offline. Need original provider, geometry and working live validation. No May Day/Montrose shoreline negative. |
| Daphne alternate https://www.skylinewebcams.com/en/webcam/united-states/alabama/daphne/daphne.html | Live fetch returned 502 Bad Gateway. | Unverified alternate; do not count as independent of Hampton Inn until scene/source identity resolved. |
| Daphne CamStreamer https://camstreamer.com/live/stream/60617188-overlooking-mobile-bay-delta-from | Search-discovered listing only. | Recovery lead; playback and physical identity unresolved. |
| FOX10 https://www.fox10tv.com/weather/cams/ | Official page lists Battleship, Bankhead Downtown, Dauphin Island, Downtown Mobile from Dauphin's, Admiral, Beach, D'Iberville. Retrieved content provides still-image references, not verified live playback. | Battleship/Bankhead/Dauphin Island are environmental candidates; exact view and timestamp required. Downtown/Admiral lower priority; D'Iberville outside target. |
| WKRG https://www.wkrg.com/weather/live-cams/ | Search lists Daphne/Dauphin Island; live text fetch yielded weather/navigation/login UI, not validated camera playback. | Unverified directory, not an observation. |
| Fairhope Yacht Club https://fairhopeyachtclub.com/ | Official homepage loaded; no live camera link found in retrieved homepage. | Do not claim a working camera; broader site coverage not exhaustive. |
| Check the Bay https://didyoucheckthebay.com/livecams | Directory search lists Fairhope Pier, Sea Lab, Mobile Bay Delta; page extraction exposed only shell. | Discovery only; resolve each original provider and deduplicate. |
| DISL aquarium https://www.disl.edu/aquarium/ | Official search excerpt explicitly describes its Mobile Bay camera as the largest tank in the Mobile Bay gallery. | Exclude that aquarium camera from wild-bay biological evidence. Do not assume an unrelated Sea Lab directory link is the same camera without checking. |

## Admission and next work
1. Restore/verify Fairhope and Grand Hotel live access first; then test the Daphne source routes and FAA/FOX10 environmental candidates.
2. Use permitted public viewers. Verify actual advancing live playback near live edge across two observations 10–30 seconds apart, plus scene progression; record measured interval and unknown source delay. For periodic-image cameras, establish documented refresh/capture timestamps before proposing a separate approved admission contract.
3. Describe actual visible shoreline and minimum usable detail. Small organisms may be unresolvable; bird concentrations and anonymous human search activity are contextual signals, not independent Jubilee confirmation.
4. Keep metadata and structured observations only: source, physical-camera independence group, time/zone, visibility, freshness evidence, visible extent, activity, confidence, media_retained=false.
5. Frozen, dark, obstructed, inaccessible or unverified views remain UNKNOWN. Absence of activity is scoped to the visible area and sampled interval, never a whole-shore non-event.
6. No camera subscriptions, outreach, image archive, new paid vision calls or production changes were made. Apply AGENTS.md repeat-outreach permission requirement before any future contact.

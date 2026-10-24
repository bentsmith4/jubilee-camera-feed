# J10 historical social reporting: two-event timing and coverage audit

Research date: October 15, 2026 (America/Chicago). Existing owner: Research & Calibration; Jubilee Dot coordinates consumption. Research only; no event admission, control promotion or forecast change.

## Finding

Public reporting supports occurrence corroboration and sometimes a public-post clock. These two selected, already-reported events do not validate reporting sensitivity, six-/twelve-hour onset-to-report detection, or P(no event | no retrieved report). Ben's proposed 80% remains an untested hypothesis. Current accepted baseline is 15 Tier-B candidate mornings, zero Tier-A controls and zero clean training negatives.

September 2020 has two reproducible ID-derived creation times and a newly recovered, retrospectively published Montrose observation account. June 2024 has a same-day news clock and a traceable Facebook video pointer, but still no independently verified first social-post timestamp or onset/end pair. No recovered item establishes the earliest public report across all platforms.

## Reused work and scope

Consulted current AGENTS, Dot charter, shared work register, canonical portfolio ledger version 37, open PRs, event history, source registry, historical event evidence, human-observation recovery and June 12 May Day contrast. Repository read baseline: `62c389e76601e8695fc8dc93b125d0479f71d941`. No competing social-reporting PR was found. PR #91 time-of-day assessment remains separate; its historical inventory was not repeated. These are provenance additions to J10, not a second event database, scheduler or research owner.

The canonical 2020 ID is `2020-09-07-fairhope-labor-day`; the 2024 ID is `2024-06-12-point-clear-south-grand-hotel`. The new Montrose account is not automatically equated with the exact Orange Street pocket or admitted as an additional event.

## September 7, 2020

| Source / clock | Recovered value | Meaning and limitation |
|---|---|---|
| Tiff original status `1302983245928292354`, linked by WSFA | 2020-09-07 09:53:08.744 CDT; 14:53:08.744 UTC | ID-derived object creation; candidate posting clock. WSFA preserves author, date and firsthand report context. Current original response was not recovered. |
| Tiff video status `1302984266255683585`, linked by WSFA | 2020-09-07 09:57:12.009 CDT; 14:57:12.009 UTC | Same author/source chain, 4m03.265s later; not a second independent event or duration measure. |
| Existing Devon Walsh screenshot evidence | Approximately 07:30 local, September 7, held in canonical event record | Existing reported activity time; original permalink/publication metadata still unresolved. Do not overwrite it with Tiff's posting time. |
| Communicating Science video `0pzBi2ijl-Q` | Narrated approximate 07:00, September 7, in Montrose | Description and retrieved transcript identify activity about half a mile north from Steadman's Landing; exact onset/end and device clock unverified. |
| Same YouTube video's page metadata | `2020-11-29T18:57:03-08:00` = November 29 20:57:03 CST / November 30 02:57:03 UTC | Both uploadDate and datePublished match. Provider summary displays November 30; raw offset explains the date difference. This was published about 83 days later, not during the September event. |
| WSFA current metadata | datePublished September 10 05:29:51.210 CDT; dateModified 05:29:01.345 CDT | Modified precedes published by 49.865s. Visible page labels an update; URL contains September 9. These are publisher fields with inconsistent semantics, not independently established first publication. |

The newly recovered Montrose description reports little activity near the Sibley entrance before moving north. That is evidence of reported spatial heterogeneity, not a negative for the entire cell. Author identity/lineage independence from other 2020 material is unverified. The 07:00 narration, 07:30 screenshot and 09:53 post cannot be joined into one exact-site onset-to-report delay without proving spatial and source linkage. No onset, continuous duration or cessation time is independently anchored.

Snowflake reproduction uses integer arithmetic:
`unix_ms = (int(status_id) >> 22) + 1288834974657`.
X's official documentation confirms that Snowflake IDs encode creation time and warns against floating-point ID precision loss. Both IDs were independently recalculated with Python integers and JavaScript BigInt. Decoding proves arithmetic given the preserved identifier; it does not independently authenticate the current post content, visibility history or earliest-report completeness.

Direct Twitter requests returned 403; X retrieval was disabled; the public oEmbed endpoint returned 404. None of these responses proves the posts were deleted or absent historically.

Sources:
- https://www.wsfa.com/2020/09/09/something-that-only-happens-two-places-world-just-occurred-mobile-bay/
- https://twitter.com/tiffofthesouth/status/1302983245928292354
- https://twitter.com/tiffofthesouth/status/1302984266255683585
- https://www.youtube.com/watch?v=0pzBi2ijl-Q
- https://docs.x.com/fundamentals/x-ids

## June 12, 2024

| Source / clock | Recovered value | Meaning and limitation |
|---|---|---|
| Same-day 1819 News account | First reports about 06:00; sightings off Zundel Road near Grand Hotel | Reporter relays Facebook-group reports. Approximate reported alert time, not an original platform timestamp. Narrative describes sunrise; this does not establish precise onset. |
| Original video pointer recovered through 1819 | https://www.facebook.com/1467160029/videos/1220539962448168/ | Stable source-chain target. Retrieval throttled; creator/time/media not independently verified in this run. Do not decode Facebook numeric IDs as X Snowflakes. |
| Lagniappe same-day article metadata | datePublished/dateCreated `2024-06-12T15:45:00-05:00`; modified June 19 18:03:35 CDT | Earliest exact timestamped June 12 news item recovered here. Publisher-attested metadata, not proof it was the day's earliest report or independently archived public availability. |
| Lagniappe accessible introduction/caption | Janet McGlothren; photos credited to her and Explore Eastern Shore; south of Grand Hotel, before sunrise | Useful named eyewitness/source lineage. Full article is access-restricted; encoded text beyond the paywall was not decoded or used. Exact observed time remains unresolved here. |
| Outdoor Life direct eyewitness interview | Published June 13 12:57 EDT = 11:57 CDT | Jake Markris describes a friend's phone alert followed by filming at Point Clear on Wednesday. Private call time and capture clock unknown. Not proof of independent original social publication. |
| Embedded Outdoor Life YouTube video `ar3-6ZEPaBs` | uploadDate/datePublished June 13 10:14:33 PDT = 12:14:33 CDT | Next-day publication clock; no event-onset or device capture timestamp recovered. |
| Coastal Angler | June 27, 2024, 18:16 displayed; timezone unspecified | Retrospective by 15 calendar days. Explore the Eastern Shore/Facebook credited; original post not recovered. Its general duration discussion is not June 12 duration evidence. |

1819's May Day observations remain the existing scoped contrast, not a new clean negative. Its 05:30 conditions update must not be treated as the timestamp of the separate no-event check. Public wording about sunrise and Lagniappe's before-sunrise account may differ in precision/site/observer; preserve both instead of selecting an invented onset.

Sources:
- https://1819news.com/news/item/jubilee-brings-sealife-to-surface-near-grand-hotel-wednesday-sunrise
- https://www.facebook.com/1467160029/videos/1220539962448168/
- https://www.facebook.com/groups/3246895562306338
- https://www.lagniappemobile.com/news/jubilee-spotted-south-of-point-clear/article_bab010a0-28fc-11ef-ae8a-d3983d6663b6.html
- https://www.outdoorlife.com/fishing/video-jubilee-alabama-coast/
- https://www.youtube.com/watch?v=ar3-6ZEPaBs
- https://coastalanglermag.com/mobile-bay-experiences-first-jubilee-of-the-summer/

## Search completeness and geography

| Source family | Actual coverage in this investigation | Consequence |
|---|---|---|
| X/Twitter | Two original permalinks preserved by one publisher; direct access/oEmbed unsuccessful; exact-ID search found no additional result | Known posts, not a complete historical timeline, reply set or deletion history. |
| Facebook | Indexed public leads and 1819 source links; direct video/group fetches throttled; alternative scrape did not yield usable content | No complete dated group search, pagination or public-visibility history. Broad results reused generic snippets; cannot count as independent event reports. |
| Nextdoor | Public web queries for 2020 Montrose and 2024 Point Clear returned unrelated/current neighborhood material | No dated historical neighborhood archive or member-only search was inspected. Not measured historical silence. |
| YouTube | Two specific public video pages, metadata and available transcripts | Publication and narrated event clocks separated; no complete channel/site inventory or original media/device-clock validation. |
| News / local sites | WSFA, 1819, Lagniappe public excerpt/metadata, Outdoor Life, Coastal Angler | Uneven retrospective survival; overlapping source chains and paywall limits. Search/index discovery time in 2026 is not availability to a 2020/2024 forecast. |
| Private communication / direct observation | Existing owner evidence reused; no new private accounts, calls or field observations | Unobserved alerts and unreported localized events remain possible. |

The two dates span reported Montrose/Fairhope and Point Clear pockets. They provide no systematic coverage denominator for Daphne/May Day, Fly Creek, Battles or Mullet Point. A large shoreline event can coexist with little activity at a nearby entrance. Do not extrapolate one reporter's locality to the entire Eastern Shore.

Executed query families included both exact event dates/locations, the Tiff status ID, Facebook-specific June 12 Point Clear terms and Nextdoor-specific date/locality terms, using two web engines and Firecrawl as recovery. General searches sometimes returned unrelated festivals/cruises or snippets recycling another article. Retrieved results were screened; no numeric source-coverage percentage is inferred. The companion JSON records exact queries and result classes.

## Six-/twelve-hour verification and silence

Three distinct targets require separate evaluation:

1. Occurrence corroboration: the retrieved material supports the already-confirmed historical positives, with site/time qualifications.
2. Timely detection: no case here has independently established onset plus first-public-report completeness and historical search availability. Therefore neither six-hour nor twelve-hour reporting sensitivity can be estimated. The 2020 09:53 candidate post makes same-morning verification plausible for that known event; it is not a measured general success rate.
3. Non-occurrence inference: an empty search cannot distinguish no event, unobserved event, private reporting, delayed posting, deletion or failed indexing/access. Keep UNKNOWN.

Reporting sensitivity P(report by h | event) differs from P(no event | silence). The latter additionally depends on event prevalence and the chance of silence when no event occurred. Two selected positives found through reporting supply neither denominator. Even independently verified posting times would not validate 80% confidence by themselves.

## Existing J10 next gate and Dot handoff

Use an independently ascertained event/known-effort control cohort, defined before examining reporting. Freeze shoreline cell, event size/visibility criteria, verification window and six-/twelve-hour deadline. For each episode retain onset/active/end intervals and their uncertainty, first observer time, source post creation/public visibility, collector retrieval time, query/access/pagination effort and source lineage. Exact first-report status requires a bounded declared source universe; otherwise label earliest recovered only. Retrospective/current visibility does not prove historical as-of availability.

Validate reporting detection on held-out episodes/seasons with uncertainty and site/size strata. Deduplicate authors, reposts, media reuse and news syndication. Use repeated searches only within a separately authorized existing workflow; this report creates no collection schedule. Social outcome evidence must not leak into earlier forecast features. No clean control, probability, weight or model change until scientific gates close.

Current disposition: research recorded; first-report/onset/coverage validation remains BLOCKED_EVIDENCE. Native Jubilee Dot acknowledgment is PENDING: https://chatgpt.com/dots/home rendered a signed-out 404 in this session. The canonical J10 register receives the report pointer and next gate; this is repository handoff, not proof of Dot consumption. Preserve Research scientific ownership, Sensing observation effort, Dawn validity ownership and existing schedules. No outreach or paid model analysis was performed; ordinary web retrieval tools were used. No third-party image/video was downloaded or retained.

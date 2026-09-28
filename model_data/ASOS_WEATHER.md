# Official ASOS observed weather

The September 27 snapshot (`7facbe9b74a9865ad4a98a239b6dedab12785a12`)
correctly rejected KBFM/KMOB wind observations about three hours old and kept
blank precipitation UNKNOWN. This path supplies current machine-readable
observations without relaxing that policy or changing forecast weights.

## Source choice

Use NOAA/NWS Aviation Weather Center (AWC),
`https://aviationweather.gov/api/data/metar?ids=KBFM%2CKMOB&format=json&hours=6`.
One bounded request covers both airports, including METAR/SPECI reports. Pick
the newest observation separately for each station, breaking ties by source
receipt time for corrections. Do not backfill missing fields from older reports
or replace one airport with the other.

- [Official API documentation](https://aviationweather.gov/data/api/) describes
  machine-to-machine METAR access, JSON, hourly updates at most stations, custom
  User-Agent guidance, rate limits, and HTTP 204 for no data.
- [Official OpenAPI schema](https://aviationweather.gov/data/schema/openapi.yaml)
  defines `obsTime` as UNIX observation time, `receiptTime` as source receipt
  time, wind in knots/degrees, and precipitation in inches over 1/3/6/24 hours.
  These native units and separate periods are retained.
- [NWS general API documentation](https://www.weather.gov/documentation/services-web-api)
  notes that station observations can be delayed up to 20 minutes by upstream
  MADIS QC. AWC is the primary path here because it directly exposes aviation
  reports with observation/receipt/raw-report provenance. This is an engineering
  choice, not a measured availability guarantee or proof of the September 27
  table-delay cause. No scraped weather table, forecast, or third-party mirror
  is used as an observed-weather fallback.

The official schema and a live two-station response were checked during
implementation. Both airport identities, coordinates, time fields and wind
units matched. Precipitation was absent in that response and remained UNKNOWN.
KBFM/KMOB are airport observations and regional context for the Eastern Shore;
neither represents measured Point Clear/Daphne shoreline wind, rainfall or DO.

## Time and admission rules

| Field | Meaning |
| --- | --- |
| `observed_at_utc` | Actual AWC `obsTime`; sole age basis. |
| `received_at_utc` | AWC `receiptTime`, preserved separately; null if absent. |
| `source_report_time` | Original AWC `reportTime`; not used as observation/availability time. |
| `available_at` | First successful local retrieval of this exact decoded report, conservatively after response completion. |
| `ingested_at` | This run's retrieval time; repeated reports retain their earlier `available_at`. |

The 90-minute boundary is read from `sensor_contract.json`, not copied into a
second policy constant. Exactly 90 minutes is admitted; anything older is
UNKNOWN. Consumption checks freshness again and rejects observations or data
availability after forecast issue time. Source receipt before observation or
after local retrieval, malformed aware timestamps, mismatched station/location,
NIL/non-observation reports and station maintenance flags fail closed.
`reportTime` can be a later nominal reporting bucket and is preserved, not used
to invalidate an otherwise sound observation.

Local QC checks finite values, broad physical ranges, dew point/temperature and
gust/sustained-wind consistency. Variable/calm direction is UNKNOWN while a valid
wind speed can remain usable. These are local checks, not a claim of final
climate-archive QA. The source `qcField` is retained without inventing meanings
for undocumented bits.

Missing/null/blank precipitation is UNKNOWN, never dry/zero. Explicit numeric
zero is retained only when reported and locally valid. PNO/PWINO invalidate
precipitation. A reported trace remark with a decoded quantity is `TRACE` with
no exact numeric amount; it cannot become zero or the decoder's nominal trace
quantity. Period totals are never summed or interpreted as overnight coverage.
Missing gust, direction or rain does not discard independently valid wind speed.

## Products and dawn consumption

- `asos_weather_manifest.json`: run status, retrieval times, raw archive SHA-256,
  rejected timestamp records and normalized-data SHA-256.
- `asos_weather_normalized.json`: latest per-airport parameter rows conforming
  to the sensor contract, with original source values and local QC. Rejected
  values are null. They must still be checked for freshness when consumed.
- `current_asos_weather.json`: evaluated per-station/per-parameter admission
  snapshot for shared dawn context. `KNOWN`, `TRACE` and `UNKNOWN` are explicit.
- `public_archive/asos/<sha256>.json.gz`: immutable original public response
  bytes, compressed deterministically; no camera data.

Run a fresh retrieval with `python model_data/ingest_asos_weather.py`. For an
isolated diagnostic use `--out-dir /tmp/jubilee-asos`.
Before a dawn brief, re-evaluate at the actual issue time:

```sh
python model_data/ingest_asos_weather.py --snapshot-only --as-of 2026-09-28T06:44:12-05:00
```

This prints an evaluated snapshot; it does not rewrite the historical
`current_state_snapshot.json`, forecast probabilities, or earlier dawn evidence.
Offline replay requires the manifest/data pair available for that issue; a
later retrieval cannot be backdated. `build_readiness.py` uses this same
evaluation function at its own run time. The dawn input contract points to the
new products and requires this check rather than trusting a saved KNOWN label.

## Workflow and failure behavior

`sensing_quality.yml` retrieves ASOS before building readiness and includes all
three products and public raw archives in artifact upload and Git persistence.
Its existing three-hour cadence alone cannot satisfy 90-minute weather freshness,
so `asos_weather.yml` refreshes only this small request hourly at minute 07 UTC.
The jobs share a concurrency group to prevent simultaneous weather writes.
The hourly workflow does not run rivers, NGOFS2, cameras, vision or forecasts.
Existing non-LLM GitHub ingestion schedules are year-round under seasonal policy.

Hourly scheduling is best effort, not a freshness guarantee. Workflow delays,
station outages or transport failures still produce UNKNOWN; the dawn consumer
can selectively refresh. The September 28 06:44:12 CDT timing recorded in
`85f3824e75640f195496cffee8d30fb13f911173` is unchanged. Repository contract
integration is not proof that the external ChatGPT dawn task has consumed the
new files; verify its first post-merge run separately.

Fetches use a custom User-Agent, 20-second request timeout, three bounded attempts
for transient failures, a 2 MB response cap and six-hour lookback. Each run
invalidates prior products before network access. HTTP/network unavailability
and HTTP 204 publish UNKNOWN without claiming successful weather coverage;
malformed payloads publish UNKNOWN and fail the workflow visibly after the
products are persisted. Manifest/data hash mismatch also reads as UNKNOWN.
Parser exceptions are not silently retried forever. Successful download status
is separate from per-field freshness/coverage.

## Validation

```sh
python -m unittest discover -s tests -p 'test_asos_weather.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
```

Offline tests include the September 27 stale-wind/blank-rain regression, both
stations, exact freshness boundary, issue-time availability, receipt/clock QC,
corrections/duplicates, missing/zero/trace rain, calm/variable wind, bad values,
outages/empty/malformed responses, retry bounds, raw-hash integrity and readiness
integration. Fixtures are synthetic and are never committed as live evidence.
ASOS remains descriptive input with zero new production weight; no model
recalibration, threshold change, or forecast skill claim is included.

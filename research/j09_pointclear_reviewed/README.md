# Mobile Bay ship-channel ADCP offline research

This directory decodes GRIIDC `Y1.x122.038:0002` into auditable research tables.
It is **decoded research, not scientifically accepted current data**. Every
velocity row retains `validated_current=False` and `production_weight=0`.
Nothing imports this directory from camera runtime, forecasting, readiness or
scheduled workflows. Python 3.11+ and its standard library are sufficient.

Dataset: [Kyeong Park, ADCP transecting data along the ship channel of Mobile
Bay](https://data.griidc.org/data/Y1.x122.038:0002), DOI `10.7266/N7B85630`.
The provider identifies its downloadable data/metadata as public-domain CC0;
retain investigator credit and source provenance. This decoder is deliberately
scoped to the observed legacy RDI PD0/WinRiver records, not every PD0 variant.

## Lightweight tests

From the repository root, with no archive, network, expanded tables or paid API:

```sh
python -m unittest discover -s research/ship_channel_adcp/tests -p 'test_*.py' -v
```

These 13 tests cover six NMEA parsing examples, three synthetic motion-report
boundaries (empty, one pair, constant speeds), and four replay-verifier guards.
They do not constitute archive ingestion, environmental validation or skill
evidence. The corrected motion diagnostic reports undefined correlation as
`null` and emits a header-only CSV for empty selections.

## Full offline replay

Supply an existing local ZIP acquired from
`https://data.griidc.org/download/dataset/1519`. This command never downloads it.
Keep the archive and output directory outside the repository:

```sh
python research/ship_channel_adcp/validate_replay.py --archive /path/to/Y1.x122.038.0002.zip --out /path/to/new-adcp-results
```

The archive is 94,580,522 bytes. Its acquired SHA-256 is
`f0552c3aa68267dd7443f8f7ed672f32c938ed91744cee8cb967c3e5b50f18d9`.
The replay fails if that hash, any of the 68 member hashes, CRC, inventory or
supporting file hashes differ. It decodes every ensemble, runs the motion
diagnostic, runs eight real-archive/full-artifact tests, checks every velocity
row's production gates, and saves `validation_receipt.json` plus the test log.
The output directory must be new or empty to avoid stale-result acceptance.

The recorded reference replay uses the original ZIP modification time
`2026-09-28T04:25:16.517421+00:00` as acquisition time. With that preserved
timestamp, all six output hashes must match `provenance.json`. To explicitly
require this exact replay, add `--require-reference-hashes`. A later acquisition
has its own timestamp and legitimately changes timestamp-bearing outputs; do
not relabel it as the original acquisition. The verifier records those hash
differences while still requiring identical motion outputs and all data gates.

All 17 source-package tests are retained: nine lightweight and eight archive
checks. Four additional lightweight tests cover the integration verifier.
The full suite never silently skips archive tests. Direct archive-test execution
requires both `ADCP_ARCHIVE` and `ADCP_RESULTS`; use the wrapper above to create
fresh results and set them automatically.

## What the reference replay establishes

The 11 survey days yield 6,210 PD0 ensembles, 248,400 native velocity-bin rows
and 107,996 checksum-valid RMC records. Preliminary structural screens leave
138,927 bins; **zero currents and zero training labels are accepted**.
The 5,743 bottom-track/GPS speed pairs have 53 differences above 0.5 m/s and
correlation 0.9217490158546151. These are exploratory vessel-motion diagnostics;
serial samples, magnitude agreement and correlation do not establish water
current accuracy or Jubilee forecast skill.

`provenance.json` retains the acquisition/source hashes, all 68 raw member hashes,
provider inventory hashes, six output hashes, publication time, manufacturer
source URLs/hashes and unresolved gates. `provider_metadata/` preserves the
separately retrieved provider inventories and metadata. The Point Clear snapshot
is read only for its model target coordinate; it is neither live guidance nor an
observed shoreline-current source. Expanded CSVs, source ZIP and manuals remain
external. `survey_summary.csv` is a small research coverage summary.

## Scientific gates remain open

- The provider labels the instrument Nortek AWAC, while native records identify
  RDI PD0/WinRiver. Instrument provenance needs reconciliation.
- The generated ZIP differs from the provider's original checksum and size.
  All member names/sizes and ZIP CRC pass, but the original endpoint returned
  HTTP 500. Matching the acquired copy does not verify the original archive.
- GPS RMC time is UTC; the native ADCP RTC stays unlocalized. RTC offsets/drift
  and candidate embedded GGA dates need evidence before time alignment is accepted.
- Native components remain SHIP/water-relative-to-instrument. Bottom subtraction
  is only algebraic research; heading, mounting, magnetic correction, moving bed,
  bottom-track quality and motion correction remain unresolved. Earth and
  shore-normal components stay absent.
- WinRiver configured transducer depths vary from 0.25 to 1.0 m: 0.25 m on
  August 18, 0.5 m on seven surveys, and 1.0 m on September 23/30 and October 27.
  Native leader depth is zero throughout. Bin centers relative to the transducer
  and 0.5 m spacing are decoded; actual deployment depth and surface/bottom
  interpretation remain unverified. See `survey_summary.csv` for each survey.
- Correlation/percent-good and conservative bottom/side-lobe screens are retained
  as preliminary flags, never a generic scientific QC pass.
- The tracks remain approximately 8 km from the Point Clear model target, with
  no matched local oxygen or accepted event/control evidence. Registry date
  non-overlap is not proof that no event occurred.
- `available_at_utc=2016-01-07T15:38:00Z` is later than the 2010 observations.
  These records cannot enter as-of 2010 predictive inputs.

The September 24 source audit and earlier register history remain unchanged.
The appended September 28 J09 checkpoint records this local research proposal
without promoting the source registry, feature catalog, production weights or
scheduled consumers.

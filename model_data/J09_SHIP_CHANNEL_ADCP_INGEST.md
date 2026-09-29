# J09 ship-channel ADCP research ingest

Source: Kyeong Park, GRIIDC `Y1.x122.038:0002`, DOI `10.7266/N7B85630`.
The provider describes 11 survey days, 68 files and 94.58 MB. Its catalog says
Nortek AWAC, but the independently reviewed native data were RDI PD0/WinRiver.
The reviewed offline package reported 6,210 ensembles, 248,400 bins and
107,996 RMC records; those counts have **not** been reproduced by this repository.

## PointClearPC handoff reported 2026-09-29

The owner reports an acquired/generated archive copy named
`Y1.x122.038.0002_ACQUIRED_COPY.zip`, 94,580,522 bytes, SHA-256
`f0552c3aa68267dd7443f8f7ed672f32c938ed91744cee8cb967c3e5b50f18d9`.
The original retained local copy `Y1.x122.038.0002.zip` reportedly has
the same hash. A separate
`REVIEWED_INDIVIDUAL_SHA256_AND_PROVENANCE.json` reportedly contains
68 `raw_members` entries, SHA-256
`c52f0aa91b8f1592db6891cf313ba2c4eff7ec76782d2b3a749d0b7257fd1fe6`;
all 68 expanded members were reported independently rehashed with zero
mismatches. The portable proposal directory reportedly includes
`validate_replay.py`, README and `provenance.json`.

These are owner-supplied handoff receipts, **not independently byte-verified
in this repository**. The package is on PointClearPC and is not mounted in the
cloud workspace or committed to GitHub. Neither native bytes nor normalized
rows are on this PR. The original provider GET returned HTTP 500, and this
acquired/generated ZIP is **not** a provider-original ZIP; the provider ZIP
checksum remains unverified. Member name/size/CRC agreement and acquired-copy
hash do not change that status. Preserve the source as
`registered-not-ingested` until the native bytes and 68 member hashes are
transferred, independently checked and replayed.

## Independent GRIIDC download and replay — 2026-09-29

A direct GRIIDC page download yielded `Y1.x122.038.0002.zip`, 94,580,522
bytes, SHA-256
`28f00ff17d5da03b89ae5798adfbf4c4b1882d55b6c9617567a1bcab64718dd5`.
It has 68 ZIP members and passes all ZIP CRC checks. It is **not byte-identical**
to the owner-reported acquired/generated ZIP (`f0552c3a…50f18d9`), despite
equal byte count. The provider download and all 68 member SHA-256 values are
recorded in `j09_ship_channel_adcp_provider_replay_20260929.json`. The provider
ZIP and a replay bundle containing source hashes, normalized SHIP rows,
executable parser and tests were saved to persistent ChatGPT Library and
byte-for-byte read back; this is a reproducible provider-source route without
the PointClearPC path. The acquired/generated ZIP, reviewed 68-hash JSON and
portable proposal were **not** independently transferred or compared here.

On the eleven native `*_000r.000` members, the PR parser independently
produced 6,210 checksum-valid SHIP-frame ensembles, 248,400 bins and 993,600
component rows with zero rejected decoded PD0 records. The eleven TXT files
contain 109,903 RMC sentences; 108,000 are status-A and checksum-valid under
a simple NMEA screen. The offline review accepted 107,996 RMC records. That
four-record difference cannot be explained from this screen alone and must
not be silently equated with the four suspect ensemble/navigation associations.
The exact proposal filter and anomaly identifiers remain unavailable. No RMC
position was joined to any ensemble, no UTC conversion or Earth-frame velocity
was accepted, and all current rows remain zero-weight research observations.
The registry should not be promoted merely from matching these counts.

## Reproducible handoff

Preserve the exact native files immutably, including their directory names and
separate SHA-256 hashes. Invoke:

```sh
python model_data/ingest_j09_ship_channel_adcp.py --output-dir /tmp/j09-research /path/to/20100818/*.DAT
```

Supply every surveyed native DAT file explicitly; repeat for the other survey
days or pass all files in one command. Keep original relative paths externally
in the archive inventory; the parser uses basenames in output. Compare the
manifest's file sizes/hashes with the reviewed handoff before calling any run
canonical. The raw bytes are copied to immutable content-addressed `raw/` paths;
existing mismatched files fail closed. The output manifest binds each CSV row to raw SHA-256 and byte offset,
and binds the CSV by SHA-256. The parser checks PD0 checksum, section bounds,
native SHIP transform, RTC fields and missing velocity sentinel. It emits four
native SHIP components per bin (port/starboard, aft/forward, toward surface and
error velocity), not four beams; `velocity_mm_s` is not an Earth vector. Rejected
records are counted, never interpolated.

The parser deliberately leaves RMC navigation association, latitude/longitude,
timezone, availability, draft and vertical reference unresolved. Four suspect
ensemble/navigation associations in the offline review, including a roughly
294-second offset, require explicit reconciliation. Within-survey RTC continuity
cannot prove timezone or exclude between-survey resets. Legacy WinRiver
bottom-track fields may be absent or replaced. A future separate versioned
navigation/QC stage must preserve all RMC records and evidence for each match.

Before promoting any Earth-frame current: compare compatible vendor playback
for seven reviewed segments (57 native records), recover deployment, compass,
heading, magnetic variation, draft/transducer and clock metadata, validate
ship-motion correction and depth/bottom/side-lobe QC, and reconcile all four
timing anomalies. The nearest reviewed transect was about 7.94 km from Point
Clear; no local shore-normal observation or survey-date event overlap is proven.
The source remains `registered-not-ingested`, research only, zero weight.

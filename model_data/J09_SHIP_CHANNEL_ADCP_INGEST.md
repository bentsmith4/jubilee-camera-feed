# J09 ship-channel ADCP research ingest

Source: Kyeong Park, GRIIDC `Y1.x122.038:0002`, DOI `10.7266/N7B85630`.
The provider describes 11 survey days, 68 files and 94.58 MB. Its catalog says
Nortek AWAC, but the independently reviewed native data were RDI PD0/WinRiver.
The reviewed offline package reported 6,210 ensembles, 248,400 bins and
107,996 RMC records; those counts have **not** been reproduced by this repository.

## Current blocker

The reviewed source package and portable proposal were on PointClearPC, outside
the accessible repository history. Neither raw bytes nor normalized rows, the
27 individual reviewed hashes, the seven-segment packet or its executable
decoder are on main or the listed remote branches. The provider GET was reported
HTTP 500 during the original acquisition; this environment returns HTTP 403.
The provider ZIP SHA-256 is unknown. Matching reconstructed member names, sizes
and CRCs does not establish the provider ZIP identity. No raw hash, native row
count, navigation pairing or canonical ingest completion is asserted here.

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
native SHIP components per bin; `velocity_mm_s` is not an Earth vector. Rejected
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

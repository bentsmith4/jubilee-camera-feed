# J09 ship-channel ADCP research ingest

Source: Kyeong Park, GRIIDC `Y1.x122.038:0002`, DOI `10.7266/N7B85630`.
Research only. Registry remains `registered-not-ingested`; no source promotion,
forecast weights, probabilities, alerts, Earth currents or Point Clear
shore-normal currents are accepted.

## Exact PointClearPC handoff reconciliation — 2026-09-30 UTC

The exact acquired ZIP and its reviewed companions were retrieved from the
previously transferred PointClearPC handoff, without another provider download.
`Y1.x122.038.0002_ACQUIRED_COPY.zip` is 94,580,522 bytes, SHA-256
`f0552c3aa68267dd7443f8f7ed672f32c938ed91744cee8cb967c3e5b50f18d9`.
The reviewed 68-member provenance JSON independently hashes to
`c52f0aa91b8f1592db6891cf313ba2c4eff7ec76782d2b3a749d0b7257fd1fe6`.

All 68 member names, sizes and SHA-256 values match across the acquired ZIP,
reviewed expanded-member transport, reviewed manifest, saved PR38 provider ZIP
and PR38 replay inventory. All three ZIP CRC tests pass. The saved provider ZIP
independently hashes to `28f00ff17d5da03b89ae5798adfbf4c4b1882d55b6c9617567a1bcab64718dd5`.
Exactly 408 archive bytes differ. Masking **only** DOS time/date fields in the
68 local and 68 central ZIP headers makes the two archives byte-identical.
All acquired member timestamps are 2026-09-27 23:25:12; provider-download
member timestamps are 2026-09-29 10:41:54. These are ZIP metadata with no timezone
asserted. The original provider archive checksum remains unverified; neither
matching generated containers nor matching members establishes that checksum.

## RMC selection: exact four-record explanation

PR38's substring screen sees 109,903 RMC fragments. The reviewed line-start
parser sees 109,898 sentences. Both yield 108,000 checksum-valid status-A
records before the reviewed field-validity checks; 107,996 pass those checks.
The four exclusions are all in `20101021_transect/20101021_transect.TXT`:

| Source line | GPS UTC clock on 2010-10-21 | Course | Reviewed rejection |
| --- | --- | --- | --- |
| 19410 | 13:10:22 | 360.0 | invalid_rmc_speed_or_course |
| 81367 | 15:19:48 | 360.0 | invalid_rmc_speed_or_course |
| 132649 | 17:06:40 | 360.0 | invalid_rmc_speed_or_course |
| 133305 | 17:08:02 | 360.0 | invalid_rmc_speed_or_course |

The preserved decoder requires `0 <= course < 360`. Each sentence has a valid
checksum and status A; changing only course to 0.0 and recomputing its checksum
makes it pass. This independently isolates the course-range predicate. No
normalization, deletion from raw evidence or claim of physical invalidity is
made. The complete sentences, source hashes and line numbers are in
`j09_pointclear_evidence_reconciliation_20260930.json`.

These exclusions are **not the four timing anomalies**. The RMC rejection occurs
before ensemble association and cannot establish anomaly identity. The
reviewed timing-anomaly identities/vendor packet are not in this portable
proposal. Timing association and clock calibration remain scientific gates.

## Replays and verification limits

Replaying the acquired eleven `*_000r.000` members through PR38's unchanged
parser reproduces 6,210 SHIP ensembles, 248,400 bins and 993,600 component rows.
With the saved provider replay's `--ingested-at 2026-09-29T15:45:26.069692+00:00`,
normalized CSV SHA-256 is
`bdfe46f0230af7a380bab50d1b7aa2816bf444f51defc3640db21716abf147f6`,
identical to both PR38's recorded hash and the saved provider CSV bytes.

The reviewed portable decoder, provenance, inventories and tests are preserved
byte-for-byte under `research/j09_pointclear_reviewed` (Python caches omitted).
All 17 supporting-file hashes verify. Its full replay reproduces the six
reference counts, including 107,996 RMC rows and 138,927 structurally screened
bins. All 248,400 velocity rows pass the zero-weight/non-Earth gates; eight
archive tests and thirteen lightweight tests pass.

However, the original full `validate_replay.py` exits nonzero at
`motion_output_hash_mismatch_motion_consistency.json`. Linux LF JSON hashes to
`2fc5af3184c552cc90947aac01b52f25cec3175bd3dbebcc4d75ab5cac0774ec`;
serializing those exact bytes with CRLF reproduces the reviewed reference
`949fcede7762f3bce262b10ece13c81937eaca8940143029da332faf50522bb7`.
The separate `motion_pairs.csv` hash is
`3c9681860840c4458395fe07576b1453ac4ee9ac12eb5a7527e8d4513f94d7f5`,
versus reviewed `2ca3766ec70bc54f75593cd71ef94ea8d226e3f92df3d0d21bf6e1162c4a55ab`.
LF/CRLF, doubled-CR and BOM transformations do not explain that mismatch.
The original reference CSV bytes are absent from the identified handoff, so its
precise cause remains unresolved. Do not infer floating-point or row differences
from hashes alone, weaken the verifier, or claim all six outputs are identical.
The materialized archive has a new acquisition mtime; it was not relabeled as
an original acquisition to force timestamp-dependent output matches.

## Reproduce

```sh
python model_data/reconcile_j09_handoff.py \
  --acquired /path/Y1.x122.038.0002_ACQUIRED_COPY.zip \
  --provider /path/J09_GRIIDC_PROVIDER_DOWNLOAD_20260929.zip \
  --transport /path/POINTCLEARPC_REVIEWED_68_NATIVE_FILES_TRANSPORT.zip \
  --output /tmp/j09-reconciliation.json
python -m unittest discover -s tests -p 'test_j09*.py' -v
python -m unittest discover -s research/j09_pointclear_reviewed/tests -v
python research/j09_pointclear_reviewed/validate_replay.py \
  --archive /path/Y1.x122.038.0002_ACQUIRED_COPY.zip --out /tmp/j09-reviewed-replay
```

The final command retains the documented cross-platform reference-hash failure.
`reconcile_j09_handoff.py` verifies only archive and navigation-selection evidence;
the committed report additionally records the independently executed replays.
Native SHIP components retain their raw clock, byte-offset and source-hash
identity. Vessel motion, deployment/compass/draft/depth QC, Earth rotation and
shore-normal projection remain unresolved. No predictive skill is established.

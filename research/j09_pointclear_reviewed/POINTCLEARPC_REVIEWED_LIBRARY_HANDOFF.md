# PointClearPC-reviewed provenance chain — J09 GRIIDC Y1.x122.038:0002

This handoff is a PointClearPC-reviewed research package.  It is intentionally
separate from independently downloaded GRIIDC provider artifacts.

## Acquired archive

`Y1.x122.038.0002_ACQUIRED_COPY.zip` is a byte-for-byte copy of the acquired
archive retained on PointClearPC.

- bytes: `94580522`
- SHA-256: `f0552c3aa68267dd7443f8f7ed672f32c938ed91744cee8cb967c3e5b50f18d9`

It is **not represented as an original provider ZIP**.  The original provider
ZIP checksum is unverified because the original endpoint returned HTTP 500.

## Portable companion containers

`POINTCLEARPC_REVIEWED_68_NATIVE_FILES_TRANSPORT.zip` and
`POINTCLEARPC_REVIEWED_PORTABLE_DECODER_PROPOSAL.zip` are transport containers
created for Library delivery.  They are not provider archives and must never be
used to claim provider-original ZIP verification.  The former contains the 68
extracted native members; the latter contains the portable decoder, tests,
provenance, README, and replay validation tooling.

## Verification

`REVIEWED_INDIVIDUAL_SHA256_AND_PROVENANCE.json` provides the reviewed per-file
name, byte count, and SHA-256 list.  Before Library transfer, all 68 extracted
members were independently checked against it: 68/68 present, zero mismatches.

`J09_OFFLINE_REPLAY_RECEIPT_20260928.json` records the reviewed 107,996-RMC
selection and the replay conditions.  With the acquired ZIP, this manifest,
and the portable decoder proposal, `validate_replay.py` can reproduce the
reviewed selection without PointClearPC access.

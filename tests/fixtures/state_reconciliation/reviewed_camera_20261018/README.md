# Exact reviewed camera evidence, October 18, 2026

These files are unchanged bytes from merged PR #111, commit
`1b69b62b1fd7a3020c5102e082c3b0c0976c8a21`, review head
`ea35175040f248864236998f2ca2c1c0d7c5700f`, evidence base
`69b406901a63d26ee7bd59abb825e07d50451651`.

- Snapshot blob: `86593d77bc4e6da353e04600da66019bd92d493e`
- Snapshot SHA-256: `62504f99b9b0e4263a79b2b8a8030b1fe0bbdad3c4803c3fc6d2ff2656a1e24e`
- Camera fingerprint: `3893f47bffd5095379ca8a2dace154324276061d539b385cc40613f8f39f5e46`
- Review: `manual_event_review`, dated `2026-10-18T22:16:31.539511-05:00`
- Global cycle: `2026-10-18T22:06:04.956448-05:00`
- E2 back-deck last nominal shot: `2026-10-18T22:07:16.809571-05:00`

The legacy review's `capture_time_ct` equals the global cycle, not the subject's
last shot. Tests preserve both identities and the original review unchanged.
The full snapshot/forecast pair, three camera metadata documents, registry and
sensor contract are retained. No camera pixels are duplicated. Original image
hashes remain in the exact snapshot fixture. Tests generate size-correct synthetic
JPEG-marker bytes, then explicitly rebind only image provenance and the forecast
for their isolated repository. Environmental fixtures are also synthetic; they
do not claim to reproduce actual ARCOS observation values. Exact live-source
replay is a separate read-only check against the pinned main checkout.

Original review: https://github.com/bentsmith4/jubilee-camera-feed/pull/111
The explicit decision is UNKNOWN for low detectability, neither event evidence
nor a biological negative. This fixture is not fresh review authorization.

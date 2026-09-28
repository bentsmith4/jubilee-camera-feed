# Bounded desktop acceptance receipts

`desktop_acceptance_20260928.json` preserves the **actual September 28,
10:55–10:58 CDT deployment and acceptance**, from issue 26's final
[PASS comment](https://github.com/bentsmith4/jubilee-camera-feed/issues/26#issuecomment-5873737867).
It supersedes the earlier blocked deployment attempts for that execution only.
The September 6 receipt stays historical and is never used as a fallback.

The receipt binds the exact saved, sanitized preflight report and exact UTF-8
public comment body by SHA-256. `.gitattributes` preserves those evidence bytes.
Its execution window has minute precision; the report's offset-aware
`checked_at_utc` is actually expressed in CDT and must be parsed with its offset.
The report was checked at **10:57:08.821369 CDT** against the existing
**10:06:34.804851 CDT** normal capture. It is not a post-deployment canonical
capture or next-dawn acceptance. Public comment metadata was retrieved from
GitHub: author `bentsmith4`, ID `5873737867`, created/updated `15:58:47Z`.

The independently verified source SHA-256 is
`2598aa3eb1e2c6f52a6c6d1afed52b8b5e781fbc112ec545c1bf150e5281a464`.
GitHub PR 29 was merged at `15:54:30Z`: head
`26bb1b88638d0d7cb39454ba1d4ec42474636b81`, reviewed/deployed main
`d56f884596ab8709dfd78d57e5317784c2ea25d4`.

## Reproducible evidence and limits

Run `python -B model_data/desktop_acceptance.py` in a full-history checkout
with the existing test dependencies. The read-only audit verifies:

- Both required merge ancestors, PR head ancestry, reviewed source hash,
  publication's single direct parent, and publication ancestry into reviewed
  main and the checked generation.
- The exact six-camera set across registry/status/burst/vision, coherent capture
  and ordered shot identities, freshness at the actual check, byte counts,
  nine publication SHA-256/blob identities, and decoding of six public JPEGs.
- The ten changed publication paths against the publisher's existing allowlist.
- Archived evidence hashes, PASS/check codes, counts, offsets and chronology,
  and machine bindings against the archived public statement.

The report attests **27 locally verified objects**, **30 R2 GET/hash/decode
verified objects**, **18 immutable burst frames**, stable snapshot/pointer,
near-live frames, task and heartbeat health. Neither reconciliation nor this
audit contacts the desktop or R2, re-verifies private burst bytes, or claims
ongoing task/heartbeat health. The private per-object hashes and capture-ID
digest suffix cannot be reconstructed from the nine public files. This limit
is explicit in the receipt; no hashes or private verification are invented.

The first default preflight returned NOT_VERIFIED for missing remote Git
objects. The final PASS used process-only `GIT_ALTERNATE_OBJECT_DIRECTORIES`
with authentic objects from the reviewed checkout. This qualification is
retained. It does not claim that the default evidence view passed or that the
production Git object store was changed. Public provenance and hashes provide
auditable attribution and byte binding, not a cryptographic signature of
desktop execution. The reviewed repository commit remains the trust boundary.

## Reconciliation admission

`desktop_acceptance.py:RECEIPT` explicitly selects one reviewed receipt. A
future acceptance requires a new dated receipt/evidence set, review and an
explicit selector update; there is no discovery by latest filename or fallback.
The consumer reads only the reconciler's pinned committed generation. Dirty,
untracked and downloaded files cannot enter state. It reads local Git objects
with lazy fetch, replacement objects and optional Git locks disabled.

Historical PASS is retained under
`operational_fault_assessment.desktop_acceptance_receipt.historical_acceptance`
only after the historical evidence validates. Current operational PASS also
requires all of the following:

- The final comment version is available by the issue time (no look-ahead).
- The issue time is no later than capture time plus the existing camera
  freshness limit, capped at 60 minutes. Publication, receipt creation and
  subsequent reconciliation do not reset that clock.
- The current six-camera registry, all nine capture-file bytes, and reviewed
  runtime source bytes still match. Later main commits alone do not invalidate
  the receipt, provided the reviewed main remains an ancestor.

For this receipt the latest possible current admission is **11:06:34.804851
CDT on September 28**. At later issue times the operational field and each
camera's `raw_archive_verification` are NOT_VERIFIED, with STALE_RECEIPT and/or
binding reasons, while the bounded historical PASS remains durable. This is
expected. It does not erase the completed acceptance or certify later captures.

Missing or invalid receipts yield NOT_VERIFIED with explicit reasons and do
not block unrelated reconciliation. Invalid evidence cannot retain a partially
trusted historical PASS. Receipt/evidence/source hashes enter normal snapshot
provenance; receipt admission and reason codes enter consumption identity, so
expiry or revocation cannot be suppressed as a duplicate trigger. Historical
Git objects missing in a shallow checkout fail closed without a fetch.

Only operational context changes. No event evidence, non-event labels,
biological absence, probability changes, weights, relaxed UNKNOWN semantics,
fault/recovery notifications or alert gates are derived. Existing event/fault
review requirements, forecast binding, source freshness checks and the strict
`>20%` four-trigger contract remain intact. The scheduled reconciler publishes
the current pair; this PR does not insert a backdated state snapshot.

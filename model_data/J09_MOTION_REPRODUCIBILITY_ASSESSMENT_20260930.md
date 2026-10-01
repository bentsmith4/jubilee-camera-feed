# PR38 motion-output reproducibility assessment

Assessment date: 2026-09-30 UTC. Reviewed PR head:
`bb7c2f6700b4bee3e59601b6240f5b662ee5fb7c`.

## Decision

PR38 is defensible as a **research-only code and evidence merge with an open
reproducibility defect**. It is not defensible as a fully reproduced reviewed
motion dataset, a successful full-verifier run, scientific acceptance, or a
production/model improvement. This assessment does not merge or deploy it.

The completed archive/member and four-RMC-record reconciliation is carried
forward from `j09_pointclear_evidence_reconciliation_20260930.json`; it was not
repeated for this investigation.

## Recovery search and its limits

- Cloned the repository without a shallow-history boundary; fetched all 38
  advertised pull-request heads as well as the branch refs. There were 2,914
  reachable commits at the search snapshot.
- Searched reachable path history for `motion_pairs`, `ensembles.csv`,
  `navigation_rmc.csv`, the original `research/ship_channel_adcp` directory,
  motion-related paths, and named ADCP/J09 ZIP/source-package paths. No original
  CSV, intermediate input file, or original source-package directory was found.
  The motion script/test history found only the preserved proposal introduced
  by `bb7c2f6`. This is a path-history search, not a claim to have inspected
  every arbitrarily renamed blob, unreachable Git object, or private backup.
- The published release list was empty. Both current successful CI runs
  (runtime `36652282884`, research `36652282994`) had empty artifact lists.
  This does not establish that every historical workflow artifact is absent.
- Searched accessible Library titles and indexed contents for J09, ADCP,
  PointClear, ship-channel, motion CSV, and the exact reference hash. Retrieved
  and read the transferred PointClearPC handoff and original replay receipt.
  No additional original motion output or its original intermediate inputs was
  recovered. Search can miss unindexed archive contents; this is not a claim
  that no other private copy exists.
- The preserved proposal explicitly excludes `results/`, ZIPs and compressed
  CSVs. Its README says expanded outputs remain external. The transferred
  receipt reports an earlier successful replay, but contains hashes rather
  than the missing CSV bytes.
- No direct PointClearPC filesystem/execution capability was available here.
  Earlier-context retrieval supplied no additional original output location.
  The desktop disk, local-only branches, ignored outputs, backups and original
  source-package workspaces remain unsearched by this run.

## Exact remaining recovery targets

| Artifact | Reviewed SHA-256 |
| --- | --- |
| `motion_pairs.csv` | `2ca3766ec70bc54f75593cd71ef94ea8d226e3f92df3d0d21bf6e1162c4a55ab` |
| `ensembles.csv.gz` | `a0f1a8ec023968ff0f13f0f3f9344ed71046d3998502a6ba290d63f11e9f8107` |
| `navigation_rmc.csv.gz` | `2401a30463448a163bea2d3f7ba24b226d5ebd92e3b49efb7859369b6b028b49` |
| revision-2 source-package receipt | `84b3adbafb02714fc4ed3ee6c72430e6374836f60ea945541161f08a71f06bb2` |

The original receipt identifies local branch
`codex/adcp-offline-research-20260928`, research directory
`research/ship_channel_adcp`, base commit
`44c8d677578e08ada145bc48af5bef495bac4be1`, and Python 3.12.14.
These are search leads, not proof that a particular absolute output path exists.
The known September 29 handoff is not a substitute for the original results.

The preserved `motion_consistency.py` reads exactly two data files:
`ensembles.csv.gz` and `navigation_rmc.csv.gz`. It filters navigation flags,
sorts navigation timestamps, applies the ensemble proximity/bottom-component
conditions, selects nearest RMC candidates, computes scalar speeds, and writes
11 CSV columns. CSV order follows ensemble input order; equal-distance candidate
selection follows the script's candidate order. These are code dependencies,
**not diagnoses of the observed mismatch**.

Recover either the reference CSV itself, or both original intermediate files
with their reviewed hashes, the preserved generator, and original execution
environment/provenance. The raw acquisition, decoder and metadata are already
preserved upstream inputs; they have not established byte-identical regeneration
of the original intermediate files in this execution. A version string alone
does not capture a complete execution environment.

The motion generator does not read `ingested_at_utc`, archive modification time,
or the live Point Clear coordinate. Acquisition-time differences can change
the intermediate-file hashes but do not directly explain the motion CSV
mismatch. Do not alter timestamps to manufacture reference identity.

## What the mismatch establishes

Current recorded replay SHA-256:
`3c9681860840c4458395fe07576b1453ac4ee9ac12eb5a7527e8d4513f94d7f5`.
It differs from the reviewed motion CSV hash above. Therefore that replay does
not satisfy the recorded byte-identity contract. The earlier reconciliation
already excludes the tested LF/CRLF, doubled-CR and BOM transformations as
explanations; no such transformations were repeated here.

The separate motion JSON reproduces its reviewed hash when serialized with
CRLF, according to the completed reconciliation. This supports reproduction
of that aggregate report's content. An aggregate report does not encode every
pair field or row ordering and cannot establish CSV identity.

Without the reference bytes or validated reconstruction, the mismatch cannot
identify changed rows, changed fields, row ordering, numeric precision,
floating-point behavior, serialization cause, platform cause, reference-hash
error, or scientific impact. It establishes neither semantic inequality nor
semantic equality. Counts and summary statistics cannot close that gap.

The historical receipt's six-output replay assertion remains historical
evidence; the current independent replay has not reproduced that assertion.
Neither deleting the assertion nor treating it as current verification is
appropriate.

## Why research-only integration remains defensible

The PR diff adds research ingest, preserved proposal/evidence, tests and the
research CI invocation. The inspected workflow/runtime/model Python references
do not wire the proposal into forecasting or camera execution. Source registry
and priority files have no PR diff. The source remains registered-not-ingested;
native SHIP outputs remain research-only and zero-weight, with accepted Earth
and shore-normal currents unresolved.

Both named CI workflows succeeded at the reviewed head. Inspection of
`.github/workflows/research_quality.yml` confirms that it runs repository and
portable lightweight tests, **not** the external-archive full reference verifier.
Green CI is evidence for those checks only. The preserved full verifier still
requires exact motion-output hashes and must continue to fail when they differ;
on the recorded Linux replay its first reported failure is the motion JSON
hash, before the CSV check can be reached.

Research integration is defensible only while the following boundaries hold:

1. Retain the original verifier and reference hashes unchanged. Do not replace
   the reference hash with the replay hash or suppress the failure.
2. Keep the unresolved motion CSV defect explicit in PR/research documentation;
   do not call the full replay passing or all six outputs identical.
3. Keep source promotion, production weights/probabilities/alerts and accepted
   geometry/current transformations unchanged. No predictive skill is claimed.
4. Retain original evidence and carry a separate recovery/validation gate before
   relying on exact reviewed pair rows or accepting scientific current products.

These conditions permit preservation and further research on independently
reconciled raw data and code. They do not waive the motion reproducibility
contract or any scientific gate.

## Closure criteria

Preserve recovered candidate bytes before running anything that could overwrite
them. Hash each candidate. If the reference CSV is found, compare exact bytes,
then parse and compare schema, ordered rows and keyed fields with the replay;
report measured differences, duplicate keys and tolerance choices explicitly.
If only original inputs are recovered, verify their hashes and replay the
unchanged generator in a separate output directory with recorded environment.
An exact output-hash match closes byte reproduction; a semantic comparison
alone must not be reported as a hash-contract pass.

If the original remains unavailable, retain the reference as unresolved.
A future independently reviewed baseline would be a new baseline with its own
provenance, not retroactive verification of the missing original.

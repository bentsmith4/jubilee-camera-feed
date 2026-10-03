# J18 cache measurement and compression validation - October 3, 2026

Research only. Nothing imports these tools from the desktop runtime. No API calls,
runtime installation, camera/cadence changes, synthesis suppression, model swap,
probability/weight/threshold changes, forecast/alert changes or schedule changes
are made. The 9 PM reporting gate is preserved.

## Verified evidence

`receipt_20261003.json` comes from a read-only snapshot of the desktop's real
`frames/api_usage.jsonl`, whose SHA-256 is recorded in the receipt. The snapshot
contains 4,748 attempts from September 8 through October 3 at 09:10:06 Central:
4,746 output-bearing completed attempts, zero failed attempts and two other-status
attempts. No malformed/duplicate rows were found. October 3 is partial.

All 4,748 rows lack capture binding, capture-integrity binding, runtime version,
actual service tier, billing context class, prefix identity and cache-write counts.
These fields remain UNKNOWN, not zero. The current checked-in logger is pinned
in the receipt; its runtime-version constant is not stamped on individual usage
rows. Reading the current script cannot establish the version of old requests.

The exporter records time in America/Chicago and groups by date, fixed clock bin,
stage, model, runtime, tier, context and prefix identity. The 04-08 bin is not
claimed to be the astronomical dawn window. Missing runtime/context/prefix data
prevent causal explanations of cache misses or mixed-rate account pricing.

Within the accounting layer's September 19-October 1 window, measured cache-read
fractions of input are:

| Workload | Attempts | Cache-read fraction |
| --- | ---: | ---: |
| Montrose bird | 418 | 40.14% |
| Montrose boat | 417 | 16.28% |
| Montrose shoreline | 418 | 40.33% |
| Point Clear E2 deck | 369 | 23.82% |
| Point Clear E2 bay mouth | 417 | 40.18% |
| Point Clear E3 | 363 | 23.86% |
| Synthesis | 288 | 0.00% |

These are measured input fractions, not demonstrated reusable-prefix rates.
The lower E2/E3 fraction can reflect larger inputs; it does not itself show fewer
prefix hits. The boat deficit is still a diagnostic target, not an achieved gain.
The 2,690 attempts in this window reconcile with 2,688 completions plus two other
statuses in the merged accounting. No actual invoice saving is established.

## Export and prospective binding

```sh
python model_data/j18_measurement/measurement.py \
  --usage /local/private/api_usage.jsonl --key-file /local/private/random-key \
  --output /local/research/sanitized_attempts.json \
  --report /local/research/cache_diagnostic.json
python -m unittest discover -s tests -p test_j18_measurement.py -v
```

Use a privately generated random key of at least 32 bytes. Provider request and
response IDs, canonical private capture IDs, prompts, image data and arbitrary
extra fields are never exported. Attempt/capture/prefix references use separately
namespaced keyed HMAC-SHA256 pseudonyms. Retain the key locally to compare exports.
The committed receipt contains aggregate cohorts only; the request-level export
remains local. Raw logs and secret keys must not be committed.

Optional `--manifest` arguments accept local canonical receipts. Each receipt
must contain `capture_id`, capture timestamp, capture-time runtime version and
camera integrity metadata. A join occurs only if the underlying usage row
explicitly supplies that same `capture_id`. A nearby timestamp, attempt order,
current runtime file or a model's low-light biological UNKNOWN never establishes
the binding. Missing integrity evidence remains UNKNOWN; explicit failure remains
false. Cross-camera integrity requires all six camera receipts.

Future usage rows may provide `billed_service_tier`, `billing_context_class`,
`prompt_prefix_sha256`, `cache_write_tokens` and `cache_write_semantics` if the
provider/account telemetry genuinely supplies them. Requested tier, input length,
configured cache TTL and cache-read counts cannot substitute for billed conditions
or cache writes. Only documented `partition_of_input` writes can enter the
existing disjoint-input accounting; otherwise write semantics remain UNKNOWN.
No such fields are reconstructed for historical requests.

To close the gap prospectively, a separately reviewed telemetry-only logger must
stamp each attempt with explicit capture identity, runtime and the actual response
usage/service-tier fields, and locally fingerprint the exact stable prefix. Bind
these to canonical integrity receipts; reconcile cache-write accounting to provider
usage/billing evidence. This PR prepares the exporter and contract but does not
install a new production logger. Complete-cycle cost, observed dawn cost and actual
account spend remain UNKNOWN until both binding and billing evidence are present.

## Frozen compression candidate and held-out gate

`candidate_instruction.txt` proposes lossless single-line compact JSON, preserving
every field and safety rule. `protocol.json` is preregistered before any replay.
The corpus pins both files' SHA-256. It contains zero real cases and is explicitly
BLOCKED: historical event dates are not labeled camera frames, and quiet model
outputs are not independently verified negatives. Social silence is prohibited
as a negative label. No synthetic case is passed off as empirical effectiveness.

The existing low-light regression fixture survives exact serialization roundtrip:
9,217 pretty-printed UTF-8 bytes become 7,640 compact bytes (17.11% fewer bytes).
This is an offline format check, not fewer API output/reasoning tokens. Billed-token
savings, event-sensitivity change, false-alert change, UNKNOWN behavior change and
safety behavior change are all UNKNOWN. The merged hypothetical 4.79% scenario
saving remains a sensitivity, not a measured result from this candidate.

```sh
python model_data/j18_measurement/validate_compression.py \
  --output /local/research/compression_validation.json
python model_data/j18_measurement/build_receipt.py \
  --usage /local/private/api_usage.jsonl \
  --output /local/research/receipt.json --export /local/research/attempts.json
```

Real paired cases require independent EVENT, geometrically scoped NON_EVENT,
UNKNOWN and SAFETY labels and evidence provenance, frozen before replay. Keep
each event/site-morning and its frames/bursts together; exclude all development
groups. Pin media, rubric and unchanged downstream decision code. Replay the same
six cameras, model, runtime, tier/context, reasoning settings and synthesis policy;
record run order/cache state and all charged retries/failures. Candidate and baseline
must produce complete valid structured output and decisions through that unchanged
adapter. Independently adjudicated `unknown_preserved` and `safety_correct` receipts
must cover dark/occluded views, confounders, anonymous people, ambiguous/clear
alligators and near-people hazards, not just a correct final event boolean.

The evaluator reports paired event sensitivity, scoped false-alert rate, UNKNOWN
preservation and safety correctness, with descriptive Wilson intervals. Cost sums
all charged attempts including reasoning once, with unknown-write bounds under
the existing configurable price scenario. Missing usage does not become free work.
Any event loss, added false alert, UNKNOWN/safety failure, unmatched condition or
insufficient independent groups blocks review. Thirty groups per label is a screening
minimum, not a powered equivalence claim; a separate preregistered power analysis
is required before considering a production trial. Even a clean result returns
ELIGIBLE_FOR_REVIEW_ONLY and never authorizes deployment.

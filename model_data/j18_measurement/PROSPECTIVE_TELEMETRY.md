# J18 prospective attempt telemetry — October 3, 2026

Research-only PR. The proposed desktop change adds local fields to the existing
`api_usage.jsonl` logger. It has not been installed on PointClearPC. Requests,
models, prompt bytes, cache configuration, retry policy, synthesis decisions,
six-camera coverage, cadence, schedules, 9 PM reporting gate, probabilities,
weights, thresholds, forecasts and alerts are preserved.

## Evidence contract

| Field | Source and limit |
| --- | --- |
| `attempt_id` | Fresh UUID for each existing `responses.create` invocation, including failed calls. SDK-internal HTTP retries are not exposed by this wrapper; these rows are invocation attempts, not an audited wire-attempt count. |
| `capture_id` | Exact `capture_time_ct` already used as the canonical observation-effort identity. Matching status/burst identity and the actual objects loaded for analysis are required. This is explicitly **not** the later R2 `capture_manifest.json` seal ID, which depends on post-analysis vision bytes. |
| `capture_input_hashes` | SHA-256 of exact status/burst source bytes loaded during this invocation. Hash mismatch or concurrent replacement prevents canonical receipt binding. |
| `input_image_sha256` | SHA-256 of decoded image bytes actually sent in this request, in request order. No images, prompts, model output or error text are logged. |
| `runtime_version` | Version stamped by the invoked logger on every successful or failed API invocation. Historical rows remain unchanged. |
| `actual_service_tier` | Returned response `service_tier`, separate from the requested tier. Missing on failures/older responses remains UNKNOWN. Processing tier does not establish the account's invoice rate. |
| Usage | Existing returned input/output/total, cached-input and reasoning-output counts retained; returned `usage.input_tokens_details.cache_write_tokens` added. Missing is UNKNOWN; returned zero is zero. |
| Cache-write semantics | For returned GPT-5.6 Luna write counts only, the checked October 3 provider guide's cost equation defines writes as `partition_of_input`. The guide URL is stamped. Other models or absent counts remain UNKNOWN; count is never reconstructed from input minus cache reads. |
| Stable prefix | SHA-256 over canonical UTF-8 JSON of the exact developer role/content items including cache breakpoints. Dynamic suffix/images excluded. This is an application prefix identity, not the provider's tokenizer/cache-object identity. |
| Cache options | Actual existing request mode/TTL/retention retained; cache key fingerprinted. These are requested options, not evidence of a write or hit. |
| Billing context/tier/rules | UNKNOWN. No verified account rules are available in this repository; prompt length, requested tier, TTL and public list pricing cannot substitute. |
| Canonical integrity | UNKNOWN in the attempt row until readback against a retained canonical observation-effort snapshot matches **both** the explicit capture identity and status/burst hashes. Failure remains false; missing or ambiguous receipts remain UNKNOWN. |

Provider references checked October 3:

- https://developers.openai.com/api/docs/guides/prompt-caching — returned write/read counters and disjoint input-cost equation.
- https://developers.openai.com/api/reference/cli/resources/responses/methods/create — returned processing service tier may differ from requested tier.

The provider does not supply this application's capture identity, canonical camera
integrity, runtime code identity, application prefix fingerprint, R2 readback or
account-specific billing context in an ordinary Responses result. The wrapper
also cannot enumerate SDK-internal transport retries. All these limits are explicit;
no inferred historical backfill or actual-dollar saving is claimed.

## Canonical integrity readback

Run locally against retained canonical `observation_effort_snapshot.json` records:

```sh
python model_data/j18_measurement/readback_telemetry.py \
  --usage /local/private/api_usage.jsonl \
  --snapshot /local/private/retained-observation-effort.json \
  --output /local/research/telemetry-readback.json
python -m unittest discover -s tests -p test_attempt_telemetry.py -v
```

Use additional `--snapshot` arguments for other captures. Missing, expired,
unreadable, mismatched or duplicate candidate evidence is a gap (unreadable input
causes the command to fail). No nearby-time joins, favorable receipt selection or
social-silence negatives are allowed. The command never writes source logs or
production files. Canonical camera-integrity checks describe the upstream receipt's
metadata/latest-image/vision checks; they do not independently verify the biology,
all three burst images or an R2 archive. Actual sent-image fingerprints are retained
for a subsequent exact-media audit; a matching canonical summary does not establish
that every sent burst frame passed archive readback.

Cross-camera readback needs all six canonical camera rows. Each attempt remains
represented independently; export uses the invocation UUID, so retries/failures
are not silently collapsed by a repeated provider ID. The exporter preserves
stamped runtime and actual returned tier, accepts explicit UNKNOWN write counts,
and keeps account spend/observed dawn cost UNKNOWN.

The included validation receipt is an offline fixture result, **not** a live
PointClearPC acceptance receipt. Live prospective acceptance still requires a
completed six-camera cycle, raw-log readback, retained canonical snapshots and
an independent transport-attempt/account-billing reconciliation. Logs, keys and
request-level media fingerprints stay local; only aggregate acceptance receipts
should be committed. Existing public usage-summary publication is unchanged.

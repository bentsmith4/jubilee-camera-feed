# J18 / PR #78 economic measurement — October 15, 2026

**Measured invoice savings: UNKNOWN. Conditional published-price estimate: about 9% less per complete six-camera cycle; 6% after allocating all logged partial/rejected-cycle work to completed cycles.** Neither establishes causal PR #78 savings or the 50% operating-season target.

## Validated scope

PointClearPC was reached directly. The installed analyzer still hashes to `b1e90549dd0151ccc61e3b970cd128dacb0b4583f5170ff94f910e2cd0389e05`. Installation was October 9 at 02:17:35 CDT; October 10 is the merge/acceptance date. No redeployment or paid call was performed.

The existing J18 `readback_telemetry.py` reconciled exact capture identities and status/burst input hashes against 203 retained canonical snapshots at repository commit `62c389e76601e8695fc8dc93b125d0479f71d941`. The local utility, its existing integrity binder and `j18_cost_accounting/accounting.py` match pinned main after normalizing line endings. Existing `cost_parts` performed pricing; no parallel monitor or scheduler was created.

7,050 local rows parsed with zero invalid records. October 8–14 contains 1,323 invocation records: 1,322 completed and one incomplete synthesis. There are zero logged failed invocations and zero duplicate attempt/provider response IDs; SDK-internal HTTP retries remain unobserved. All records report `gpt-5.6-luna`, returned processing tier `default`, explicit cache-write counts and partition-of-input semantics. Requested and billed tiers remain UNKNOWN.

Of 206 candidate cycles, 22 lack exactly one output-bearing completed analysis from every camera; one additional cycle fails the strict canonical-integrity gate. The remaining 183 cycles have six completed camera observations, three sent images each, matching archived status/burst inputs and **18/18 exact sent-image hashes**, totaling 1,098 completed camera observations. This is evidence integrity and coverage, not biological effectiveness. All 77 accepted cycles without a synthesis call have independent `deterministic_quiet` receipts; absence was not assumed to mean zero work.

## Comparable costs at published prices

Baseline: October 8, 28 accepted complete cycles. Post: October 10–14, 128 accepted complete cycles. October 9 is excluded from this full-day comparison because installation occurred during that day. October 15 is partial and excluded. Complete calendar periods do not imply complete camera coverage.

| Per accepted six-camera cycle | Before | After |
| --- | ---: | ---: |
| Input tokens | 45049.11 | 44793.07 |
| Cached-read tokens (subset of input) | 12928.50 | 12478.25 |
| Cache-write tokens (subset of input) | 1267.50 | 1153.75 |
| Output tokens, including reasoning | 5901.57 | 4844.09 |
| Reasoning tokens (subset of output) | 1675.29 | 1796.05 |
| Camera analyses only, USD | 0.01312877 | 0.01182465 |
| Camera analyses plus observed synthesis, USD | 0.01382795 | 0.01258312 |

Primary estimated reduction: **$0.00124483 per complete cycle (9.0023%)**. At the same 28 complete cycles as the baseline day, the estimated saving is **$0.03486/day**. The existing 32-cycle J18 scenario yields **$0.03983/day**. These are equal-work scenarios, not changed schedules or verified daily bill reductions.

| Sensitivity | Estimated reduction | USD saved per equal 28-cycle day |
| --- | ---: | ---: |
| Complete cycles, observed synthesis | 9.0023% | 0.03486 |
| Post cycles reweighted to baseline hour-of-day mix | 8.6994% | 0.03368 |
| Complete cycles, equal synthesis-call rate | 9.8684% | 0.03821 |
| All logged work, including incomplete/rejected cycles, per accepted complete cycle | 6.0057% | 0.02470 |

The last row divides **every logged attempt's cost** in each comparison period by accepted complete cycles. Baseline cost becomes $0.01468982 per completed cycle; post cost $0.01380758. It includes the incomplete synthesis's 800 output tokens (664 reasoning) and partial coverage expenditure. This operational-efficiency sensitivity avoids calling lower coverage a saving, but includes acquisition and integrity differences unrelated to PR #78. It is not a pure compression effect.

Synthesis attempt frequency rose from 0.5000 to 0.59375 per accepted cycle. Camera-only cost fell 9.9333%. Reasoning in the full pipeline rose from 1,675.29 to 1,796.05 tokens/cycle; shorter total output is not evidence that reasoning was reduced. Input's ordinary, cached-read and cache-write partitions are priced separately.

The original 05:00–07:00 CDT comparison remains a sensitivity: strict integrity accepts six pre and six post cycles, producing an estimated 8.9395% full-cycle reduction. The original seven-pre-cycle token receipt is retained as history; this stricter audit excludes its incomplete-synthesis cycle from successful-cycle pricing but charges that attempt in the all-work sensitivity.

## Rate basis and second check

Official model pricing and caching documentation were reopened October 15:
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna): $0.20 ordinary input, $0.02 cached reads, $1.20 output per million; cache writes cost 1.25 times ordinary input ($0.25/million).
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): cache writes and reads partition input.

Formula: `((input - cached - writes)*0.20 + cached*0.02 + writes*0.25 + output*1.20)/1e6`. Reasoning is already in output; images are already in input. Maximum individual request input was 9,933 tokens, below the documented 272K long-context boundary.

All 1,323 usage arithmetic/subset checks passed. An independent integer-weighted formula reconciled all seven daily list-price totals to the existing accounting function within 1e-12 USD. Returned processing tier is verified; account-specific billed tier, discounts, credits, endpoint/region conditions and final charges are not.

## Billing blocker and minimum private export

No independently reconcilable Jubilee API charges were found in the inspected local project files, deployment receipts or authorized Hotmail billing/receipt searches. This does not establish that no billing records exist. ChatGPT subscription/Work credits do not price this API workload.

**Minimum additional evidence:** hourly UTC aggregate usage and cost for Jubilee's API project only, from **October 8, 05:00 UTC through October 15, 05:00 UTC (exclusive)**. Preserve locally confirmed project scope; export model, billed tier/rate class, attempt/status counts, ordinary/cached-read/cache-write/output tokens, reasoning subset where available, gross usage charge, credits/discounts/adjustments, net charge, currency, effective rate dates and completeness/finalization. If hourly aggregation is unavailable, supply exact CT-day buckets covering the same boundaries; ordinary UTC daily totals straddle the comparison days.

No account/project/key/request identifiers, credentials, prompts, outputs, images or raw logs are needed in the aggregate export or public repository. Provider attempt and token totals must reconcile to the local hourly aggregates; unexplained SDK retries, other workloads and unallocated charges remain explicit residuals. A total invoice or prepaid-credit purchase alone cannot establish PR #78 savings. Historical applicable prices must be confirmed before treating today's public rates as actual historical charges.

Even reconciled charges support an observational before/after result, not a randomized causal effect or detection equivalence. Actual cost per cycle/day and actual saving remain null until this gate closes.

## Existing ownership and Dot coordination

Record under existing **J18-PR78-COMPACT-JSON**. Research & Calibration retains measurement ownership; Jubilee Dot coordinates the remaining billing/effectiveness gates. The canonical companion receipt is [j18_pr78_economics_20261015.json](j18_pr78_economics_20261015.json). Raw logs, per-attempt bindings and media fingerprints remain private on PointClearPC.

Dot instruction: consume this dated report and companion receipt once, acknowledge their exact versions in the existing work register, and continue billing reconciliation from these results. Do not repeat ordinary-cycle acceptance, paid calls or deployment; do not create another ledger/monitor/schedule. Native Dot acknowledgment is **PENDING**: the existing Dot UI presented signed-out/404 state in this session. Repository delivery is distinct from native consumption.

PR #76 camera-value investigation remains independent. No cameras, frequency, resolution, models, probabilities, schedules, thresholds, alerts, UNKNOWN semantics or 9 p.m. America/Chicago restriction changed.

# J18 remaining API cost opportunities — October 28, 2026

**Decision: retain all six cameras, three-frame bursts and existing cadence. The strongest next candidate is a cache-policy-only comparison of the shared camera prefix at 30-minute versus 12-hour retention. Its conditional benefit is small: about 1.76% per standardized six-camera work unit. Further output compression has greater modeled potential, and image/token reduction greater still, but neither has established biological or safety equivalence. No candidate is ready for deployment on this evidence.**

Owner: existing Jubilee Model Research & Calibration; coordinator: Jubilee Dot; stable work ID: J18-PR78-COMPACT-JSON. This is an extension of existing accounting, not a new workstream, scheduler, inference run or deployment. PR #118 stays open, draft and unmerged; wind work remains deferred.

## Evidence and what is already implemented

- October 28 usage-summary blob ` f1fb5c54afe8c266c24885b8548bcc77ac955217` (generated 14:10:33 UTC) reports October 27 Central-day totals: 199 completed requests, 179 camera and 20 synthesis; 1,340,826 input, 368,064 cached-input, 145,549 output and 54,352 reasoning tokens. Cached input is 27.4505% of input; reasoning is included in output. No failed requests were logged that day. Counts do not establish complete, usable cycles or independent transport-attempt counts.
- A bounded read-only PointClearPC check of existing api_usage.jsonl independently reproduced these totals and found 38,624 cache-write tokens, all from the boat camera. All 199 rows have partition_of_input semantics, 30m explicit cache options, and valid token arithmetic; billed tier remains UNKNOWN. No capture or API inference was triggered. Source read-byte SHA-256: `2509fa588310fa6cfb97431da25a1f92885e02a2cfae2624e9d229c824790505`. Raw records, identifiers and media remain private.
- PR #78 compact JSON is already installed. The October 15 audit accepted 183 complete six-camera/18-image cycles across its audit window. Its primary pre/post comparison estimates $0.01382795 versus $0.01258312 per accepted cycle, 9.0023% lower, or 6.0057% lower when all partial/rejected work is charged to accepted cycles. These are conditional public-rate estimates, not invoice savings or causal effects.
- The earlier same-model, six-camera morning comparison measured 1.3002% fewer input and 19.6993% fewer output tokens; uncached input remained 29,181/cycle. Do not count installed compact-output, stable-prefix caching, compact synthesis inputs or existing deterministic-quiet synthesis again as new savings.
- The October 22/24 acceptance work found no retained same-18-image original/compact real-model output pairs with independent positive and difficult/UNKNOWN labels. Repeating that archive search without new evidence is not an experiment. Detection equivalence and actual billing remain blocked.

Sources: [usage summary](../api_usage_summary.json), [installed compact receipt](j18_compact_prompt_deployment_20261008.json), [accepted-cycle economics](J18_PR78_ECONOMIC_FINDINGS_20261015.md), [October 24 recovery](j18_dot_acceptance_reconciliation_20261024.json), [runtime](../desktop_runtime/analyze_frames.py), [camera order](../desktop_runtime/camera_policy.py), [J18 accounting](j18_cost_accounting/README.md).

## Equal-work normalization and rate assumptions

For October 27, define one standardized unit as the sum of each camera's token totals divided by its own completed-request count, plus synthesis totals divided by 30 completed Montrose-shoreline reference requests. Five cameras have 30 completions; E2 deck has 29. This pays for one analysis of each of six cameras and 20/30 synthesis calls. It does not mistake the missing deck completion for savings and is NOT a verified complete-cycle denominator.

Per unit: 45,022.1667 input; 12,344.5333 cache reads; 1,287.4667 cache writes; 4,876.5885 output, including 1,820.2644 reasoning tokens. Conditional cost is **$0.0126986969/unit**, or **$0.3555635 per equal 28-unit day**. Twenty-eight is the prior J18 comparison scenario, not a schedule change. Camera analyses contribute 93.7128% and synthesis 6.2872%; output contributes 46.0827%.

Use existing J18 rates: ordinary input $0.20, cached input $0.02, 30m writes $0.25, output $1.20 per million. Official model/caching documentation reopened October 28 confirms these public rates and 12h writes at $0.50/million. Formula:
`((I-C-W30-W12)*0.20 + C*0.02 + W30*0.25 + W12*0.50 + O*1.20)/1e6`.
Never add images to input or reasoning to output again. Rate class, discounts/credits, region/endpoint, billed tier, historical applicability, retries and reconciliation residuals remain material unknowns. Public prices do not establish account spending.

[Model pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna) · [Caching rules](https://developers.openai.com/api/docs/guides/prompt-caching) · [Inherited rate file](j18_cost_accounting/pricing_assumptions.json).

## Remaining alternatives

All dollar figures below are conditional incremental sensitivities from the October 27 mix. They are not achieved savings and must not be added indiscriminately.

| Alternative | Conditional saving per six-camera unit | Equal 28-unit day | Share of modeled cost | Evidence and material assumption |
|---|---:|---:|---:|---|
| Shared camera prefix: 12h instead of 30m retention | $0.00022341 | $0.00626 | 1.76% | Existing-arrival replay gives two 12h writes instead of 17 30m writes on October 27; same prefix, key, content and work; higher write price included |
| Further 10% reduction in camera output, including reasoning | $0.00054953 | $0.01539 | 4.33% | Hypothetical, beyond installed PR #78; all fields and detection behavior must survive |
| Further 10% reduction in visible camera output only | $0.00035585 | $0.00996 | 2.80% | More defensible compression sensitivity when reasoning is unchanged; alternative to preceding row, not additive |
| 25% smaller synthesis input | $0.00011046 | $0.00309 | 0.87% | Same synthesis rate and outputs; every evidence/timing/UNKNOWN field needed for decisions retained |
| Eliminate every remaining synthesis call | $0.00079839 | $0.02236 | 6.29% ceiling | Not recommended: existing quiet gating already skips safe cases; remaining ambiguity, missingness, low visibility and safety cases still need synthesis |
| E2 deck and E3 input reduced to shoreline's input-token footprint | $0.00162880 | $0.04561 | 12.83% | Illustrative 8,144 fewer ordinary input tokens/unit, same cache/output; token difference is not a measured image-only cost or an achievable image-quality-equivalent reduction |
| Cheaper vision model / routing | Not estimated as achievable | Not estimated | 50% lower camera cost would imply 46.86% overall before routing/fallback overhead | No validated cheaper equivalent model or independent event challenge set; model price alone is insufficient |
| Exact same-capture retry-result reuse | Not yet estimable | Not yet estimable | Depends on duplicate successful paid work | Reuse existing J16c; must prove identical camera, ordered images, timestamps, metadata, rubric, model/code and validated result; never reuse across new captures |

The two high-input cameras have 9,839 and 9,823 input tokens/request versus shoreline's 5,759. Cropping/downscaling must remain with the existing archive/image experiment owner, preserving all three frames and full-field safety review. Their larger footprint justifies research, not loss of offshore, tiny-animal, dim-light or peripheral evidence.

Other options: shorter stable prompts save only cached-read cost on hits and can destroy cache eligibility; blind prompt shortening is not automatically economic. Synthesis has zero reported cache reads/writes despite explicit caching: measure its eligible stable-prefix length against the documented 1,024-token minimum before changing keys or adding content. Do not pad merely to chase cache hits. Batch/deferred processing may suit separately authorized offline research, but cannot be counted as a live-monitoring saving unless detection latency is preserved. Lower output caps can truncate JSON or safety fields; lower reasoning effort is a model-behavior experiment, not lossless compression. Lossless image transport-byte compression is not proof of fewer billed image tokens. Wind/camera/frame suppression, perceptual deduplication and seasonal shutdown are excluded from equal-work savings.

## Completed no-charge cache diagnosis and replay

The boat camera is first in camera_policy; all six camera stages share one prefix fingerprint and one key fingerprint. Every eligible camera row on October 27 has exactly 2,272 prefix tokens partitioned between reads and writes. Boat has 13 reads and 17 writes; the later five cameras have reads only. The low boat hit rate is consistent with warming the common cache, not a unique defective boat prompt. Reordering calls would relocate that first-write charge.

Replay method: sort retained camera request-start proxies (recorded completion time minus elapsed_seconds); use exact prefix/key identity; begin each day cold; write on the first request and whenever the fixed 12h lifetime expires; otherwise read. No capture scheduling or inference is simulated. Each eligible October 20–27 day needs two 12h writes. October 21 is excluded from cost inference because four records have unknown usage. On the other seven days, modeled recorded-work savings range from $0.00565728 to $0.00722496/day; these raw-day figures are robustness checks, not equal-coverage savings.

October 27 baseline prefix charge:
`(38624*0.25 + 368064*0.02)/1e6 = $0.01701728`.
Candidate:
`(4544*0.50 + 402144*0.02)/1e6 = $0.01031488`.
Difference: **$0.00670240 over the 179 observed camera requests**, or **$0.0002234133 per shoreline reference unit**. Equalizing the missing deck analysis adds the same read cost to both arms. The corresponding equal 28-unit saving is $0.00625557; a 13-unit dawn scenario is $0.00290437 using this whole-day mix, not measured dawn costs.

Assumptions: stable eligible 2,272-token prefix; same model, key, content and request order; 12h cache eligibility; two rather than 17 writes; no new failures, latency penalties or calls; both arms use applicable public rates. With 179 calls and this baseline, the prefix scenario saves money at at most eight 12h writes; nine or more erase the benefit. Do not warm the cache with extra paid calls. Long retention on changing images/dynamic fields can add expensive writes; limit the proposal to the existing stable camera prefix.

This improves the billing category mix, **not the number of input tokens processed**. Cache hits are not result reuse: every ordinary observation still gets a new model response. Independent Decimal arithmetic reproduced October 27's normalization and cache saving; request arithmetic/subsets passed 199/199 checks. No current live payload/file equality or new complete-cycle acceptance is claimed.

## Strongest next experiment and deployment gates

**Next action within existing J18: prepare a cache-only 30m-versus-12h candidate, then seek the existing owner's gated canary approval after outstanding acceptance prerequisites.** Keep the installed PR #78 and its rollback. The offline economic replay is now complete; do not repeat it or PR #78 installation acceptance without new inputs. No paid replay or production change was executed or authorized by this report.

1. **Content and coverage gate.** Verify exact installed runtime and request fingerprints; change only stable-prefix lifetime. Require identical model, rubric, prompt content, ordered 18 image bytes/detail and all observation/output fields. Preserve six cameras, three frames, capture timing, probabilities, thresholds, alerts, UNKNOWN and 9 p.m. Central gate. Any content or image difference converts this to a higher-risk experiment.
2. **Detection and safety gate.** Reuse existing J18/PR #76 challenge-set ownership. Require independent positive biological labels and difficult negatives/UNKNOWNs, including glare, rain/wake, dim light, missing cameras, transient/distant activity, ambiguous and clear alligators, and near-people safety cases. Same-image comparisons must measure incremental misses, false alerts, uncertainty downgrades, temporal persistence and event lead time; group correlated views/frames by independent event. No new safety miss or UNKNOWN-to-negative conversion is acceptable. Predeclare an owner-approved statistical noninferiority margin; zero observed regressions alone is not equivalence. For illustration, zero extra misses in 300 independent true-positive cases gives only an approximately 1% one-sided 95% upper bound on the incremental-miss probability, not proof of zero risk. Such data do not currently exist.
3. **Operational gate.** If separately approved, use ordinary scheduled requests only, with time-block allocation long enough to model cache lifetime and cross-arm cache carryover. Do not duplicate images/calls or alter cadence to manufacture hits. Bind usage to accepted complete six-camera cycles and deterministic-quiet receipts; include rejected/partial/retried work in a second denominator. Check schema validity, coverage, failure rate, p95 latency and safety history against baseline. Freeze unrelated prompt/model changes; rollback at any coverage/safety/schema regression.
4. **Economic gate.** Log actual read/30m-write/12h-write partitions, prefix/key versions, returned and billed tiers, attempt status, latency and exact capture integrity through existing telemetry. Obtain legitimate private project-scoped provider charges, effective rates, credits and retry totals, reconcile hourly UTC/CT-day boundaries and residuals. Require positive net savings at equal accepted work after write premiums and fallback overhead. Report measured tokens, conditional cost, reconciled billed cost and causal inference separately.
5. **Authority and coordination.** Research & Calibration remains executor on its existing schedule; Dot consumes this result under J18-PR78-COMPACT-JSON. No new automation, ledger or duplicate crop/model experiment. Direct Dot-Page reconciliation is distinct from autonomous Dot acknowledgment. PR #118 remains deferred and must not be merged/deployed on its current findings.

**The 50% operating-season objective remains unachieved.** The best low-risk candidate is worth testing for correctness and recurring efficiency, not because its sub-cent equal-day saving is material by itself. Larger savings require independently validated changes to the dominant camera input/output workload.

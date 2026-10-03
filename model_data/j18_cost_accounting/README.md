# J18 conditional cost accounting — October 2, 2026

Research only. This layer adds accounting to the stable token-efficiency audit at
`f2ae704bd79205852efa895875b3eaf625981ca9`; it makes no production changes.
The 50% operating-season directional target remains unachieved. Equal event
detection effectiveness is unproven.

## Reproduce and configure

```sh
python model_data/j18_cost_accounting/accounting.py \
  --pricing model_data/j18_cost_accounting/pricing_assumptions.json \
  --usage model_data/j18_cost_accounting/usage_20261002.json \
  --output /tmp/j18_cost_report.json
python -m unittest discover -s tests -p test_j18_cost_accounting.py -v
```

The frozen sanitized usage export is exactly Git blob
`eeef7e54ad2d40d96cf1f5430258f919c256e713`, referenced by the October 2 audit.
Its SHA-256 is `3eb9f5eb7e47ff9ae30208c6c45766758dd5878abb56e42e5daf601a279b9b7e`.
No raw logs, IDs, account details, credentials, prompts or media are added.
`report_20261002.json` is deterministic and contains the assumptions and full
per-stage/per-day breakdown. New inputs or rates require regeneration.

Rates are **configurable assumptions, not verified account prices**. The checked-in
scenario uses public GPT-5.6 Luna Standard short-context direct API list rates,
retrieved October 2: $0.20 ordinary input, $0.02 cache read, $0.25 cache write,
and $1.20 output per million tokens. Sources:

- https://developers.openai.com/api/docs/models/gpt-5.6-luna
- https://developers.openai.com/api/docs/guides/prompt-caching

The model page also identifies long-context multipliers. Account service tier,
endpoint/region uplift, credits/discounts and request-level context size are not
in this aggregate export. Change the configuration when supported billing
evidence identifies them; split groups by rate class upstream if mixed rates
apply. No automatic alias mapping or price fallback is permitted.

## Accounting and comparable work

Cost = ((input − cached − writes) × ordinary rate + cached × read rate +
writes × write rate + output × output rate) / 1,000,000.
Reasoning is already within output. Images are already within input. Neither is
added twice. Cache-write counts are absent from current telemetry: the range
allows writes between zero and all non-read input. These are conservative bounds
**conditional on the configured rates and input partition**, not statistical
confidence intervals or bounds on the actual invoice. The zero-write component
breakdown is labeled as a scenario, not observed cache-write behavior.

Reference work is an output-bearing completed Montrose shoreline request (164
baseline, 418 postdeployment). A six-camera standardized reference unit sums
each camera's charged tokens per completed camera analysis, plus all synthesis
tokens per reference request. This pays for one completed analysis from every
camera rather than treating omitted camera work as savings. A second comparison
also holds synthesis calls/reference at the baseline rate. All reported attempt
tokens, including incomplete attempts, remain in the numerator; only completed
work gets denominator credit. Failed requests with missing usage block pricing.

Daily/stage absence, missing token counts, duplicate groups, unknown rate mappings,
invalid subsets and partial comparison days fail closed. The input currently has
2,688 completed requests, zero failed requests and **two other-status synthesis
requests** (September 20 and 24), hence 2,690 logged requests. The original
completed/failure audit remains correct but does not describe these other statuses.

Camera request work ratios are 96.24% baseline and 95.77% postdeployment relative
to six times reference work. They are not valid-cycle coverage percentages.
Request counts lack cycle IDs, retries, capture-integrity binding and latency.
Complete valid six-camera cycle cost therefore remains UNKNOWN; count ratios
cannot establish it. Shorter calendar-day volume is never itself efficiency.

## Conditional estimates

Both periods are priced at the same list-rate assumptions. Baseline September
9–13 and postdeployment September 19–October 1 exclude partial October 2.

| Comparable unit | Baseline USD range | Postdeployment USD range |
| --- | ---: | ---: |
| Six-camera standardized reference request, observed synthesis rate | 0.017649–0.020119 | 0.013918–0.015556 |
| Representative dawn, 13 reference requests | 0.22944–0.26155 | 0.18093–0.20223 |
| Representative complete day, 32 reference requests | 0.56477–0.64381 | 0.44536–0.49780 |

Thirteen dawn calls represent four hours at 20-minute spacing including endpoints.
Thirty-two day calls are a rounded postdeployment mean of 418/13 = 32.1538.
These configurable scenarios use whole-period token/cache mix; daily aggregates
cannot recover actual dawn-specific prices. They do not change the scheduler.
Mean cost of actually logged work per calendar-complete day is $0.55551–0.63291
baseline and $0.42591–0.47554 post; those figures are **not comparable-work savings**.
Calendar-complete does not mean continuously healthy sensing.

The conditional six-camera cost reduction range is 11.86–30.82% at observed
synthesis rate, or 9.24–28.78% holding both camera and synthesis work constant.
Range endpoints allow independent unknown write fractions in each period.
The original 7.8618% token reduction is unchanged; pricing weights are a different
metric, not a newly achieved runtime gain or actual billed-dollar saving.

## What dominates, and what candidates could save

In the zero-write scenario, camera analyses account for 93.73% of standardized
cost; synthesis 6.27%. Point Clear E2 deck and E3 each contribute about 19.1%
(38.24% combined). Billed output including reasoning is 51.07%, ordinary input
47.10%, cached reads 1.84%. With maximal unreported writes, total input billing
exceeds output billing. Input tokens cannot be split into image versus prompt
cost from this export, and reducing reasoning alone is not an evidenced option.

| Candidate sensitivity, no deployment recommendation | Conditional saving per reference request | 13-call dawn | 32-call day |
| --- | ---: | ---: | ---: |
| 10% less camera output, unchanged input/synthesis | $0.000667 | $0.00867 | $0.02135 |
| Boat camera caching reaches lower measured peer rate, before extra writes | $0.000252 | $0.00328 | $0.00807 |
| Same cache candidate with one extra full write of added input per extra read | −$0.000098 | −$0.00128 | −$0.00314 |

The output candidate saves 4.79% of zero-write scenario cost; no evidence yet
establishes that it preserves event sensitivity, UNKNOWN handling or alligator
safety. The boat cache candidate targets 1,401 additional cache-read tokens per
call using the bird/shoreline observed cache rates as a hypothetical benchmark,
not a demonstrated reusable prefix. Extra-write overhead can erase its benefit.
Even deleting all synthesis could remove only 6.27% in this scenario and would
violate the ambiguity/low-light safeguards; it is a ceiling, not a recommendation.
Candidates are separate sensitivities and must not be added as achieved savings.

The supported next research priority is to diagnose cache reuse and reconcile
cache writes/account billing, then evaluate output compression only on held-out
labeled event/non-event and safety cases. There is no evidence here supporting
camera removal, reduced cadence, cheaper-model substitution or synthesis
suppression. No new production experiment is launched by this accounting layer.

To obtain actual cycle/dawn/day costs, a separately reviewed sanitized export
must bind usage and attempt status to canonical capture IDs, camera integrity,
runtime version, service tier/context class, cache writes and time-of-day bins.
Do not publish private IDs or raw logs. Effectiveness tests must independently
measure missed events, false alerts and UNKNOWN/safety behavior before promotion.

Six-camera coverage, UNKNOWN semantics, the 9 PM reporting gate, probabilities,
weights, thresholds, forecasts and alerts are preserved.

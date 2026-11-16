# Register integrity: implementation and activation gates

Prepared under Ben's November 15, 2026 direction in existing PR #160. Not merged, deployed or enforced. Sensing remains the existing engineering owner.

## Verified scope and trust boundary

The checker requires the complete event-base register as an exact byte prefix, valid UTF-8, no NUL and newline-separated appends. The workflow verifies the proposed merge's two parents against the event base/head, logs commit and register blob identities, and executes the BASE checker in isolated Python. Missing refs/registers and identity mismatches fail closed. A candidate checker cannot approve its own history loss.

First installation has no base checker. Only PR 160 on reviewed base `952a467f9af03c17c0210a27979cdc72112c9d7a` can use candidate checker SHA-256 `5170628871f15e907380b2f6d4590a3a5daf30219224176fafee5b3e4532bdc7`. The checker is unchanged from original #160. Any pre-installation base movement requires inspection and an explicit pin update in this PR. There is no generic fallback. After installation, checker changes affect subsequent PRs after review and merge.

The workflow itself is still modifiable by a PR. This is not tamper-proof external enforcement: independent safeguard-change review remains essential. The integration tests run the actual embedded workflow program against temporary Git repositories; the bootstrap test substitutes only its synthetic fixture SHA in the test process. A passing configuration regression does not prevent workflow tampering.

This check does not validate scientific claims, referenced-file retention, source freshness, issue-window eligibility, biological detection or UNKNOWN semantics. Existing scientific/provenance gates remain mandatory.

## Corrections and concurrency

Keep all current-main bytes unchanged and append branch-only receipts at the end, retaining original event dates. Recording dates and event dates are distinct. Reconcile again if main advances. Never resolve a conflict by taking an older complete register.

Correct errors by appending a superseding receipt with the original reference, exact correction, reason, evidence, author, approval and timestamps. Exceptional historical rewrites require Ben's explicit approval of exact before/after blobs, archive, reason and bounded exception procedure. No label-based or standing bypass is implemented.

## Exact setting proposal — NOT APPLIED

| Setting | Proposed value |
|---|---|
| Branch | main |
| Required status | preserve-register; expected source GitHub Actions, with app identity verified at activation |
| Require branch up to date | true |
| Require pull request | true |
| Approving reviews | 1 independent non-author maintainer |
| Dismiss stale approvals | true |
| Code-owner review | true, after eligible independent owner verification |
| Administrators / routine bypass | enforce / none |
| Force pushes / branch deletion | false / false |
| Other effective requirements | preserve after fresh administrative readback |
| Merge queue | not proposed; workflow supports pull_request only |

Proposed CODEOWNERS coverage: `.github/workflows/**`, `tools/check_register_append.py`, `tests/test_register*.py`, this document, and CODEOWNERS itself. No independent eligible reviewer has been established; do not invent an identity or use only the PR author. This is a settings proposal, not an executable API payload with guessed IDs. An administrator must verify the effective configuration. GitHub Actions check-source identity does not authenticate workflow source code.

## Publisher compatibility blocks activation

Source inspected at main `952a467f9af03c17c0210a27979cdc72112c9d7a`:

| Existing producer | Publication path | Credential evidence |
|---|---|---|
| water_quality_ingest.yml | HEAD directly to main | contents: write; checkout default GitHub token |
| arcos_realtime.yml | HEAD directly to main | contents: write; checkout default GitHub token |
| asos_weather.yml | HEAD to event branch, normally main | contents: write; checkout default GitHub token |
| sensing_quality.yml | HEAD to event branch, normally main | contents: write; checkout default GitHub token |
| observation_logging.yml | publish_observation_record.py pushes commit to main | contents: write; checkout default GitHub token |
| current_state_freshness.yml | publish_current_state.py pushes commit to main | reconciliation job contents: write; checkout default GitHub token |
| desktop_runtime/publish_github.py | guarded commit push to main | runtime credential identity/permissions unverified; no secrets accessed |
| Human/connector register and forecast writers | other direct updates may exist | complete external-writer/account inventory still required |

`matched_control_sealing.yml` pushes to a research branch, not main. Winter water-quality ingestion stays active. PR #187 changes schedules/retrieval, not these publication paths.

Do not enable PR/check/review requirements yet: these direct writers do not obtain the required check and approval for each publication. An unrestricted bot/admin bypass defeats the safeguard. Prepare a separately reviewed migration to a validated merge path preserving throughput, retry/freshness handling, immutable evidence and winter research. Assess GitHub-token event suppression; do not assume bot PRs trigger CI. A trusted publisher alternative would need proven path confinement excluding register/guard edits, not a whole-branch bypass. No publisher migration is implemented by #160.

## Remaining acceptance

1. Reconcile latest heads and preserve current main plus branch-only appends. Keep #171's external-observation adoption gate and repair the shared season-date test fixture once in #187/shared owner path.
2. Run affected tests and exact-head hosted workflows; inherited failures remain failures. Obtain separately attributable independent review.
3. Present final commit/base/merge identities and any installation-pin update for Ben's explicit merge approval, separately from protection activation.
4. Complete publisher compatibility, independent reviewer identity and administrative readback. Present the exact consequential protection change and activation procedure for approval.
5. Validate blocking/acceptance behavior in isolation, without destructive production test changes. After an approved merge/activation, read back installed code and effective enforcement separately.

A queued assignment, green check or merged PR is not evidence of enforceable protection.

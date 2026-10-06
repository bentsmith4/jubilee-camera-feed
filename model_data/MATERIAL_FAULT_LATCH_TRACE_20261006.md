# Material-fault latch trace — 6 October 2026

Decision: PRESERVE_NEW_EXPLICITLY_ASSESSED_OPERATIONAL_FAULT. This is not reintroduction of the October 1 freshness fault cleared by PR #66. No alert or forecast policy is changed by this audit.

## Verified publication sequence

| Main history point | Evidence |
| --- | --- |
| PR #66, recovery candidate e52ee6e6053821a681bdb9f980d0a7e2a3dd8dca, merged f5e36ff9fce4528d1eb74c782d07e13049d62701 | Original freshness latch false; four-trigger condition false; suppression true. |
| 797b3c044910769ef6f92a983f841bb1accb0a44 | October 5 22:06:23 CT publication still has material fault false. The clearance survived automated reconciliation. |
| bccb0b668a67cb2e92b8c4a637e802bb18a2ac7d, committed October 5 22:30:56 CT | Explicit assessment at 22:25:58 CT changes material fault false to true and records significant Point Clear camera coverage loss. This is the first reactivation in the examined publication history. |
| 3b565cd8a105474bd6555a9a380816902cdd3782 | Publishes reviewed fault with committed current camera/sensing evidence and bound forecast. |
| 3ea6cf88a5eb004b5a1bbdc53fcad3c7854b1143 and subsequent reconciliations | Preserve the assessed latch. Generic notification text replaces the detailed original reason; it means the builder inferred no NEW fault, not that no earlier assessed fault exists. |
| PR #67, merge 79f82d5255977bb3240e32533dac41d8707d7416 | Accepts limited temporal confirmation as unresolved camera context; does not set or clear the latch. Its state already has the new latch true. |
| PR #69, horizon commit d8e5c81e962cb0f7f5dd9c8c3c6c4a6805fa00e5 | Rolls October 6–8 dates only and preserves the active gate. |

## Exact qualifying evidence

At commit 3b565cd8a105474bd6555a9a380816902cdd3782, status.json, burst_status.json and vision.json all identify cycle **2026-10-05T22:07:22.164525-05:00**.

- pcl_e2_back_deck: status ok=false, failure timestamp 22:08:41.519974 CT; burst ok=false; vision status=burst_not_ok.
- pcl_e3_bay_mouth: status ok=false, failure timestamp 22:10:20.961409 CT; burst ok=false; vision status=burst_not_ok.
- Both capture errors: CalledProcessError: capture failed; private diagnostics suppressed.
- Surviving pcl_e2_bay_mouth: three matching shots at 22:08:48.891379, 22:08:58.961427 and 22:09:09.029205 CT; vision visibility=poor, detectability=low, artificial_light_confounding=strong.
- Result: 1 of 3 Point Clear owner views remained available; total healthy owner metadata fell to 4 of 6. The explicit assessment judged this significant operational coverage loss. No Jubilee event or biological negative was inferred.

NGOFS2 forecast outages did not cause this transition. Their model context remains zero-weight SOURCE_UNAVAILABLE/UNKNOWN. The older material_fault_recovery_review remains a dated assessment of the DIFFERENT original freshness fault, not standing permission to clear subsequent faults.

## Why it remains true after camera recovery

reconcile_current_state.py takes preserved_material_fault from the preceding snapshot's material_critical_input_fault gate. It copies that gate unchanged and requires explicit review for recovery. Its operational_fault_assessment and generic notification_reason are rebuilt, so detailed activation provenance is no longer visible there. Current failed_camera_ids can therefore be empty while the previously explicitly assessed latch remains true. This is deliberate latch persistence, not proof of continuing capture failure.

This audit preserves the latch as requested for a genuinely new qualifying fault. It does not perform or claim a second recovery clearance. A later recovery decision must distinguish current restored camera health from the historical activation and be explicitly assessed.

## Validation and scope

The accepted pair at main commit 329556c7a5a7f67da7a3e94669a0ae2d52d33e36, issued October 6 08:37:19.197773 CT, was read at an exact commit. Local assertions passed for the SHA-256 of the exact snapshot bytes against forecast input_snapshot_hash, identical issue time, identical alert gates, identical notification condition, and the strict >20% comparator. It has material fault=true, notification condition=true and suppression=false.

This is an audit-only publication. Runtime code, current state/forecast bytes, probability ranges, central estimates, production weights, UNKNOWN semantics, strict >20% comparator, schedules and the 9 PM gate are unchanged. No new pair is necessary because the regression branch of the requested action did not apply and the inspected accepted pair is correctly bound.

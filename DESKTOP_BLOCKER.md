Desktop verification: September 6, 2026. The deployed publisher now creates append-only allowlisted commits using the current remote parent, preserves the working checkout, and never amends or force-pushes. Scheduled publication `cd669dd6f05c86885c4fc3f5ed94592a8ffb1e8b` retains `1a8c118d23a09a16c71ded3266e5be0afd0a6fc4` as an ancestor and preserves the model tree. See `DESKTOP_EXECUTION_REPORT.md` and `model_data/desktop_acceptance_20260906.json`. The original finding and repair contract below are retained as history. PR #2 remains unmerged.

# Publisher blocker repaired locally and verified on scheduled publication

## Confirmed finding, September 6, 2026

Two successive observed `main` tips are sibling commits, not an append-only sequence:

| Camera capture | Published commit | Parent |
|---|---|---|
| September 6, 15:06 CT | c700ca2de06c47b626e29237f5b4fc7b3bf5b078 | e02e34365d7969fbacc8c835202d3194dd69e018 |
| September 6, 16:06 CT | 1a8c118d23a09a16c71ded3266e5be0afd0a6fc4 | e02e34365d7969fbacc8c835202d3194dd69e018 |

The API confirms both were committed by Jubilee Camera Bot, with publication messages for the respective captures. This proves a non-fast-forward replacement of the observed branch tip. It is consistent with amending/replacing the camera publication commit; the local implementation has NOT been inspected, so the exact command and cause remain unverified.

Sources:
- https://api.github.com/repos/bentsmith4/jubilee-camera-feed/git/commits/c700ca2de06c47b626e29237f5b4fc7b3bf5b078
- https://api.github.com/repos/bentsmith4/jubilee-camera-feed/git/commits/1a8c118d23a09a16c71ded3266e5be0afd0a6fc4

Risk: model/data edits and camera publication share `main`. Replacing its tip can invalidate snapshot ancestry, cause merge conflicts and potentially discard concurrent work. Actual loss of a particular model file has NOT been established here. The upgrade PR also shows camera-output changes because its starting publication commit became a sibling of the new main tip.

## Required first desktop action

Before merging PR #2, inspect the actual publisher under `C:\JubileeCams`, including any Git synchronization helper called by `upload_frames.py` or `capture_publish.py`. Back up code and configuration locally. Look for `commit --amend`, force/force-with-lease pushes, replaced refs, stale base-tree construction and cached parent SHAs. Do not print credentials or authentication headers.

Implement a publication contract that cannot rewrite the model branch:
1. Main code/config/history updates must be append-only with an up-to-date parent and bounded retry on concurrent changes. Do not force-update `main`.
2. Prefer existing R2 storage for latest/archived camera media. If a replaceable Git camera mirror is retained, isolate it on a dedicated data branch within the same repository, and migrate all readers explicitly before switching writers. This is not a second project home.
3. Never publish new Montrose private images to a public branch without explicit approval.
4. Reconcile the upgrade branch against current main after the publisher is safe. Preserve current camera blobs and existing unrelated changes; do not accept older camera snapshots from PR #2. Verify the final diff contains only intended model/code/audit/public-sensor artifacts.
5. Run one real scheduled camera publication after the fix. Confirm prior model commits remain ancestors and that both camera and model files survive. Then run the upgrade tests and merge.

The 45-test suite and public-data ingestion have succeeded on the upgrade branch, but production merge is intentionally held. No Windows tasks or ChatGPT automations have been changed by the cloud session.

After resolving this blocker, execute the remaining steps in `DESKTOP_UPGRADE.md`: restore missing Montrose Pier Boat capture, onboard the shoreline camera, enforce public-source access/rights and privacy, verify archives, consolidate jobs, and run local end-to-end acceptance tests.

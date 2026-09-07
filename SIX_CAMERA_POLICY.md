# Equal treatment for all six Google cameras

Ben's September 6 instruction that all six cameras should be treated the same supersedes the earlier private-only exception for the new beach camera.

All six now share one `camera_policy.py` allowlist for near-live publication, hourly/dawn three-frame bursts, vision analysis, R2 latest/archive uploads, and append-only GitHub outputs. The separate private capture step is removed from the pipeline. Earlier local private captures are retained. Unknown cameras and credentials remain blocked.

| Camera | Google-supported protocol |
|---|---|
| Montrose Boat Camera | WEB_RTC |
| Montrose Pier Bird camera | WEB_RTC |
| Montrose Looking at Beach camera | WEB_RTC |
| Point Clear E2 Deck (SDM name Back Deck) | RTSP |
| Point Clear E2 Down the Marina | WEB_RTC |
| Point Clear Landing House Deck (legacy ID pcl_e3_bay_mouth) | RTSP |

Protocol differences are handled by the capture adapter; they do not change the publication policy. Viewing geometry and visibility still differ, and overlapping cameras are correlated observations rather than independent evidence.

The prior desktop report and private-exclusion test evidence describe the earlier deployment. This policy supersedes their private-only statements. The new six-camera acceptance report records verification after the change.

Acceptance: six successful canonical captures, six vision results, six live publications, and 18 burst images archived; all R2 object hashes verified. Prior-main ancestry and model preservation passed. Beach image was verified through the unauthenticated public image endpoint.

# Jubilee API cost optimization — September 18, 2026

## Objective

Reduce paid OpenAI vision cost without reducing six-camera capture coverage or suppressing
potential-event analysis.

## Source changes

1. **Prompt-cacheable camera prefix**
   - Stable Jubilee rubric, signal definitions, confounders, safety rules, and output contract
     now live in one developer-message prefix.
   - Camera ID, camera role, shot timestamps, and images are appended after the stable prefix.
   - GPT-5.6 explicit prompt caching is enabled with a 30-minute TTL and a stable cache key.
   - This is designed for the existing approximately 20-minute dawn-window cadence and
     repeated in-season bursts.

2. **Compact outputs**
   - Camera free-text summaries are capped at short phrases while preserving the existing
     machine fields and enum vocabulary.
   - Output token caps are 1,800 tokens per camera and 800 tokens for cross-camera synthesis.

3. **Compact cross-camera input**
   - Cross-camera synthesis receives only fields that can affect the synthesis rather than
     the entire camera response, frame summaries, and unrelated metadata.
   - Shot-timing provenance is retained.

4. **Skip redundant cross-camera model calls only when safe**
   - All six camera analyses still run.
   - The cross-camera model call is skipped only when all six cameras succeeded, visibility
     is at least fair, detectability is at least moderate, every biological signal is a clear
     negative, there is no flashlight/search signal, no alligator signal, and both Jubilee
     signal fields are `none`.
   - Any missing camera, poor visibility, low detectability, weak/possible/unclear biological
     signal, human precursor, or alligator signal still invokes the model synthesis.
   - The quiet path is deterministic and records `synthesis_mode=deterministic_quiet`.

5. **No sensing reduction**
   - Six-camera capture cadence, three-frame bursts, archived evidence, and alligator
     detection thresholds are unchanged.
   - No adaptive reduction in camera collection was introduced.

## Verification

Repository tests cover:
- API usage telemetry does not log private prompt/response content.
- Camera timing remains dynamic and outside the reusable cache prefix.
- Explicit cache controls and cache breakpoint are sent to GPT-5.6.
- Cross-camera payload excludes verbose frame summaries while retaining timing.
- A complete high-detectability quiet burst skips the synthesis model.
- Any ambiguous biological signal preserves model synthesis.

The GitHub workflow compiles `desktop_runtime` and runs the full unittest suite on pull requests
and future runtime changes.

## Deployment boundary

The repository is the reviewed source mirror. The PointClear Windows publisher does **not**
install runtime scripts from GitHub automatically. Production deployment therefore requires
replacing only `C:\JubileeCams\analyze_frames.py` with the reviewed version while the
`Jubilee Live Cameras` task is stopped, then restarting that same task. Do not create a new
scheduled task or change credentials/configuration.

Acceptance after deployment:
- a fresh `vision.json` reports
  `runtime_version=2026-09-18-cache-compact-synthesis-v2`;
- all six camera analyses remain present;
- `api_usage.jsonl` begins showing nonzero `cached_input_tokens` on repeated requests when
  cache reuse is available;
- routine fully quiet bursts may show
  `cross_camera.synthesis_mode=deterministic_quiet`;
- any non-quiet/ambiguous burst shows `cross_camera.synthesis_mode=model`.

Measured dollar savings should be reported only after at least 24 hours of in-season production
usage. No savings percentage is claimed from source code alone.

CI workflow status: repository runtime regression workflow is present on main and runs on this pull request.

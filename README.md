# Jubilee camera feed

Latest machine-readable and image outputs from the Eastern Shore Mobile Bay
camera pipeline. The production capture code runs from `C:\JubileeCams`; this
repository is the public latest-state mirror, not a second model home.

## Output contract

- `status.json`: capture-level freshness and per-camera success. A camera is
  usable only when `ok` is true and its timestamp is no more than 60 minutes
  old.
- `burst_status.json`: three canonical hourly frames per camera, now sampled at
  approximately 0, 10, and 20 seconds. Near-live single frames are a separate
  pipeline and are never substituted into the canonical burst.
- `vision.json`: per-camera temporal analysis plus cross-camera synthesis.
  Montrose's three views form one evidence site; Point Clear E2/E3 form one
  tightly clustered evidence site and are not counted as independent sites.
- `vision_rubric.json`: visual interpretation guidance.
- `model_data/event_history.json`: provenance-aware confirmed event labels.
- `model_data/sensor_contract.json`: required direct/proxy sensor fields,
  freshness limits, and QC rules.
- `model_data/model_policy.md`: separation of oxygen stress, transport, local
  geometry/detectability, and soft human-sensor evidence.

## Human-sensor guardrail

`people_present`, `flashlight_activity`, `motion_pattern`,
`clustered_search_behavior`, `temporal_persistence`, and `human_sensor_score`
describe possible shoreline searching. Slow, clustered, repeatedly focused
lights are stronger than fast linear roaming, but this signal is always a soft
precursor and can never confirm a Jubilee by itself. Low shoreline visibility,
darkness, and glare reduce detectability and confidence.

## Production guardrails

Publishing rejects capture state older than 60 minutes and rejects a
`vision.json` whose capture time does not match `status.json`. Failed or stale
cameras are omitted instead of carrying their previous image forward. Error
messages redact temporary signed stream URLs.

## Model continuity and observation logging

Read `model_data/MODEL_WORK_REGISTER.md` for current accepted work, research gaps and the owner hold on new sensors.

The subordinate `observation_logging.yml` workflow runs on camera publications with an hourly fallback. It validates one pinned camera snapshot and appends an immutable record under `model_data/observation_records/`. The fast logger is independent of slow environmental retrieval. Records include missingness and outside-window states; only sufficiently visible, fresh Montrose shoreline observations can become scoped control candidates. They are never automatically admitted as training negatives. No camera capture or alert is added by this workflow.

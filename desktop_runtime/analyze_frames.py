from seasonal_policy import require_season

if __name__ == "__main__":
    require_season()

from openai import OpenAI
import base64
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(r"C:\JubileeCams")
FRAMES = BASE / "frames"
BURST_DIR = FRAMES / "burst_latest"

STATUS_PATH = FRAMES / "status.json"
BURST_STATUS_PATH = FRAMES / "burst_status.json"
VISION_PATH = FRAMES / "vision.json"
ALLIGATOR_HISTORY_PATH = FRAMES / "alligator_history.json"
RUBRIC_PATH = BASE / "vision_rubric.json"

from camera_policy import CAMERAS

ALLIGATOR_ALERT_MIN_CONFIDENCE = 0.80
ALLIGATOR_RECENT_DAYS = 7
TZ = ZoneInfo("America/Chicago")

client = OpenAI()


API_USAGE_PATH = FRAMES / "api_usage.jsonl"


def api_response(stage, **kwargs):
    """Record token usage locally without changing request or failure behavior."""
    started = time.monotonic()
    response = None
    try:
        require_season()
        response = client.responses.create(**kwargs)
        return response
    finally:
        try:
            usage = getattr(response, "usage", None)
            record = {
                "recorded_at_ct": datetime.now(TZ).isoformat(),
                "stage": stage,
                "request_id": getattr(response, "_request_id", None),
                "response_id": getattr(response, "id", None),
                "model": getattr(response, "model", kwargs.get("model")),
                "status": getattr(response, "status", None) if response is not None else "request_failed",
                "output_text_present": bool(getattr(response, "output_text", "")),
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
            with API_USAGE_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception:
            # Telemetry must not break monitoring or mask the original API error.
            print("WARNING: API usage telemetry unavailable.")


def clean_json(text):
    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return json.loads(text)


def image_content(path):
    b64 = base64.b64encode(
        path.read_bytes()
    ).decode("utf-8")

    return {
        "type": "input_image",
        "image_url":
            f"data:image/jpeg;base64,{b64}"
    }


def analyze_burst(
    camera_id,
    camera_label,
    image_paths,
    shot_metadata,
    rubric
):

    camera_guidance = (
        rubric.get(
            "camera_role_guidance",
            {}
        ).get(
            camera_id,
            []
        )
    )

    prompt = f"""
You are analyzing THREE sequential images from one
Mobile Bay Jubilee monitoring camera.

The images are approximately ten seconds apart; use the supplied shot timestamps. They are
presented in chronological order:

FRAME 1
FRAME 2
FRAME 3

CAMERA ID:
{camera_id}

CAMERA LABEL:
{camera_label}

CAMERA ROLE:
{json.dumps(camera_guidance, separators=(",", ":"))}

JUBILEE RUBRIC VERSION:
{rubric.get("rubric_version")}

CORE PRINCIPLES:
{json.dumps(rubric.get("core_principles"), separators=(",", ":"))}

HIGH-VALUE SIGNALS:
{json.dumps(rubric.get("high_value_visual_signals"), separators=(",", ":"))}

CONFOUNDERS:
{json.dumps(rubric.get("important_confounders"), separators=(",", ":"))}

SIGNAL WEIGHTING:
{json.dumps(rubric.get("signal_weighting"), separators=(",", ":"))}

TEMPORAL RULE:
{rubric.get("temporal_rule")}

Study the THREE images both individually and as a short
time sequence.

Especially look for change between frames that could reveal:

- shrimp popping or flicking at the surface
- repeated shrimp-like surface rings
- fish jumping or breaking the surface
- fish mouths repeatedly breaking the surface
- fish gulping or "smoking"
- repeated surface boils
- animals holding abnormally at the surface
- crabs swimming at the surface
- crabs appearing/disappearing at the surface
- crabs climbing pilings or structures
- flounder, eels, rays, or other bottom fauna displaced upward
- bird diving or repeated strikes at the water
- movement toward shoreline or structure
- biological activity appearing in multiple consecutive frames

Distinguish these carefully from:

- rain drops
- normal wavelets
- changing reflections
- glare
- insects
- floating debris
- ordinary mullet jumps
- boat wake
- moving boats
- artificial light attraction
- logs or branches
- birds
- wakes or wave crests
- floating debris

ALLIGATOR SAFETY CHECK:

Inspect each frame explicitly for an American alligator. Only mark
"clear" when recognizable alligator anatomy is visible (for example
the head/eyes/snout profile, body/scutes, or tail), not merely a dark
shape or wake. Use "possible" for unresolved candidates. Never label
logs, birds, wakes, wave shadows, reflections, or floating debris as
alligators. Compare all three frames to confirm plausible persistence
or motion. "near_people" means an alligator and people are visibly in
the same local area; do not infer distance that the image cannot show.

IMPORTANT:

A feature that appears in more than one frame is more credible
than an isolated one-frame feature.

A feature that clearly changes position in a biologically plausible
way may be more credible than a stationary reflection.

Do not diagnose dissolved oxygen.

Do not invent small animals that cannot be resolved.

Return ONLY valid JSON with exactly these fields:

{{
  "visibility":
    "poor|fair|good",

  "detectability":
    "low|moderate|high",

  "water_surface":
    "flat|slight_ripple|moderate_chop|choppy|unclear",

  "rain_surface_interference":
    "none|possible|strong|unclear",

  "wake_interference":
    "none|possible|strong|unclear",

  "fish_surface_activity":
    "none_visible|isolated|possible_abnormal|clear_abnormal|dense|unclear",

  "fish_jump_activity":
    "none_visible|isolated|multiple|dense|unclear",

  "fish_gulping_or_smoking":
    "none_visible|possible|clear|widespread|unclear",

  "shrimp_surface_popping":
    "none_visible|possible|multiple|dense|unclear",

  "shrimp_surface_concentration":
    "none_visible|possible|clear|dense|unclear",

  "crab_surface_swimming":
    "none_visible|possible|clear|multiple|unclear",

  "crab_climbing_structure":
    "none_visible|possible|clear|multiple|unclear",

  "flounder_or_flatfish_shallow":
    "none_visible|possible|clear|multiple|unclear",

  "eel_displacement":
    "none_visible|possible|clear|multiple|unclear",

  "stingray_or_other_bottom_fauna_displacement":
    "none_visible|possible|clear|multiple|unclear",

  "shoreline_or_structure_accumulation":
    "none_visible|possible|clear|dense|unclear",

  "offshore_bottom_fauna_surface_aggregation":
    "none_visible|possible|clear|dense|unclear",

  "bird_feeding_activity":
    "none_visible|possible|active|dense_active|unclear",

  "people_present": "none_visible|possible|clear|unknown",
  "flashlight_activity": "none_visible|possible|clear|unknown",
  "motion_pattern": "none_visible|stationary|walking|searching|unknown",
  "clustered_search_behavior": "none_visible|possible|clear|unknown",
  "temporal_persistence": "none_visible|one_frame|multiple_frames|unknown",
  "human_sensor_score": null,
  "human_sensor_confidence": 0.0,
  "human_sensor_detectability": "good|limited|poor|unknown",
  "people_collecting_seafood":
    "none_visible|possible|clear|unclear",

  "animal_lethargy_or_abnormal_motion":
    "none_visible|possible|clear|widespread|unclear",

  "alligator_frame_detections": [
    {{
      "frame": 1,
      "visible": "none|possible|clear|unclear",
      "count_estimate": 0,
      "behavior": "none|swimming|stationary|feeding_or_striking|near_people|other|unclear",
      "location_in_frame": "short description or none",
      "confidence": 0.0
    }},
    {{"frame": 2, "visible": "none|possible|clear|unclear", "count_estimate": 0, "behavior": "none|swimming|stationary|feeding_or_striking|near_people|other|unclear", "location_in_frame": "short description or none", "confidence": 0.0}},
    {{"frame": 3, "visible": "none|possible|clear|unclear", "count_estimate": 0, "behavior": "none|swimming|stationary|feeding_or_striking|near_people|other|unclear", "location_in_frame": "short description or none", "confidence": 0.0}}
  ],

  "alligator_visible":
    "none|possible|clear|unclear",

  "alligator_count_estimate":
    0,

  "alligator_behavior":
    "none|swimming|stationary|feeding_or_striking|near_people|other|unclear",

  "alligator_location_in_frame":
    "short description or none",

  "alligator_temporal_change":
    "none|stationary|moving|appeared|disappeared|behavior_changed|unclear",

  "alligator_confidence":
    0.0,

  "artificial_light_confounding":
    "none|possible|strong|unclear",

  "repeated_surface_activity":
    "none_visible|possible|clear|unclear",

  "activity_changed_across_frames":
    "no|possible|yes|unclear",

  "likely_temporal_artifact":
    "none|rain|wake|reflection|camera|other|unclear",

  "temporal_jubilee_signal":
    "none|weak_possible|moderate|strong|unclear",

  "overall_jubilee_visual_signal":
    "none|weak_possible|moderate|strong|unclear",

  "frame_1_summary":
    "short description",

  "frame_2_summary":
    "short description",

  "frame_3_summary":
    "short description",

  "temporal_summary":
    "1 to 3 sentences describing what changed or persisted",

  "confidence":
    0.0
}}
"""

    prompt += "\nHuman observations are anonymous only. Never identify people or track identities. Score human_sensor_score from 0 to 1 only when observable (0=no visible search, 0.5=possible search, 1=clear persistent clustered search); otherwise null. This score is a descriptive weak precursor, never a Jubilee probability or confirmation. Darkness and occlusion mean unknown, not absence.\n"
    content = [
        {
            "type": "input_text",
            "text": prompt
        }
    ]

    for path in image_paths:
        content.append(
            image_content(path)
        )

    response = api_response(
        f"camera:{camera_id}",
        model="gpt-5.6-luna",
        input=[
            {
                "role": "user",
                "content": content
            }
        ]
    )

    result = clean_json(
        response.output_text
    )

    required_human = {'people_present', 'flashlight_activity', 'motion_pattern', 'clustered_search_behavior', 'temporal_persistence', 'human_sensor_score', 'human_sensor_confidence', 'human_sensor_detectability'}
    if not required_human.issubset(result):
        raise ValueError("Missing human-observation schema fields")
    score = result['human_sensor_score']
    if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1):
        raise ValueError("Invalid descriptive human score")
    if result['human_sensor_detectability'] in {'poor', 'unknown'}:
        result['human_sensor_score'] = None
    result['human_sensor_schema_version'] = '1.0-descriptive-unvalidated'
    # Machine-controlled identifiers.
    result["camera_id"] = camera_id
    result["camera_label"] = camera_label

    result["burst_shots"] = shot_metadata
    result["burst_frame_count"] = len(image_paths)

    return result


def cross_camera_analysis(
    analyses,
    rubric
):

    compact = {
        camera_id: analysis
        for camera_id, analysis
        in analyses.items()
        if analysis.get("status") == "ok"
    }

    prompt = f"""
Synthesize this burst-based Mobile Bay Jubilee camera analysis.

Each camera result was generated from THREE images approximately
one second apart.

Do not invent evidence beyond these observations.

Spatial dependence rules:

- Montrose Pier Bird and Montrose Pier Boat are the same pier system.
- Point Clear E2 Bay Mouth and E2 Back Deck are the same location.
- Point Clear E3 is only about 50 feet from E2.
- Therefore those views are not fully independent confirmations.

Biological priority:

1. shrimp popping / surface concentration
2. fish gulping or smoking
3. multiple surface-swimming crabs
4. crabs climbing structures
5. displaced bottom fauna
6. dense shoreline or offshore abnormal aggregation
7. repeated abnormal behavior across frames
8. birds/people as supporting evidence

CAMERA RESULTS:

{json.dumps(compact, separators=(",", ":"))}

Return ONLY valid JSON:

{{
  "overall_visual_jubilee_signal":
    "none|weak_possible|moderate|strong|unclear",

  "montrose_visual_signal":
    "none|weak_possible|moderate|strong|unclear",

  "point_clear_visual_signal":
    "none|weak_possible|moderate|strong|unclear",

  "temporal_confirmation":
    "none|limited|moderate|strong",

  "highest_value_observation":
    "short string",

  "highest_value_temporal_change":
    "short string",

  "important_confounders":
    ["short strings"],

  "spatial_confirmation":
    "none|limited|moderate|strong",

  "recommendation_for_next_burst":
    "short string",

  "alligator_summary":
    "short factual summary; do not treat possible shapes as confirmed",

  "confidence":
    0.0
}}
"""

    response = api_response(
        "cross_camera",
        model="gpt-5.6-luna",
        input=prompt
    )

    return clean_json(
        response.output_text
    )


def build_alligator_alert(analyses, capture_time_ct):
    """Build the safety alert deterministically from camera results."""
    detections = []

    for camera_id, analysis in analyses.items():
        if analysis.get("status") != "ok":
            continue

        confidence = analysis.get("alligator_confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        frame_hits = []
        for frame in analysis.get("alligator_frame_detections", []):
            try:
                frame_confidence = float(frame.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                frame_confidence = 0.0

            if (
                frame.get("visible") == "clear"
                and frame_confidence >= ALLIGATOR_ALERT_MIN_CONFIDENCE
            ):
                frame_hits.append(frame)

        # Require a clear aggregate detection plus either two-frame
        # persistence or exceptionally strong single-frame evidence.
        credible = (
            analysis.get("alligator_visible") == "clear"
            and confidence >= ALLIGATOR_ALERT_MIN_CONFIDENCE
            and (len(frame_hits) >= 2 or confidence >= 0.95)
        )

        if credible:
            detections.append({
                "camera_id": camera_id,
                "camera_label": analysis.get("camera_label", camera_id),
                "count_estimate": analysis.get("alligator_count_estimate", 1),
                "behavior": analysis.get("alligator_behavior", "unclear"),
                "location_in_frame": analysis.get("alligator_location_in_frame", "unclear"),
                "temporal_change": analysis.get("alligator_temporal_change", "unclear"),
                "confidence": confidence,
                "clear_frame_count": len(frame_hits),
            })

    return {
        "triggered": bool(detections),
        "priority": "high" if detections else "none",
        "capture_time_ct": capture_time_ct,
        "minimum_confidence": ALLIGATOR_ALERT_MIN_CONFIDENCE,
        "criteria": "clear aggregate detection at >=0.80 confidence and clear in >=2 frames, or >=0.95 aggregate confidence",
        "detections": detections,
        "summary": (
            f"Credible alligator detection in {len(detections)} camera view(s)."
            if detections else "No credible alligator detection in this burst."
        ),
    }


def parse_capture_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def sightings_from_vision(vision):
    """Extract only deterministic, credible alligator detections."""
    alert = vision.get("cross_camera", {}).get("alligator_alert", {})
    if not alert.get("triggered") or alert.get("priority") != "high":
        return []

    capture_time = alert.get("capture_time_ct") or vision.get("capture_time_ct")
    if not parse_capture_time(capture_time):
        return []

    sightings = []
    for detection in alert.get("detections", []):
        try:
            confidence = float(detection.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if confidence < ALLIGATOR_ALERT_MIN_CONFIDENCE:
            continue
        sightings.append({
            "capture_time_ct": capture_time,
            "camera_id": detection.get("camera_id", "unknown"),
            "camera_label": detection.get("camera_label", detection.get("camera_id", "unknown")),
            "count_estimate": detection.get("count_estimate", 1),
            "behavior": detection.get("behavior", "unclear"),
            "location_in_frame": detection.get("location_in_frame", "unclear"),
            "temporal_change": detection.get("temporal_change", "unclear"),
            "confidence": confidence,
        })
    return sightings


def load_alligator_history(previous_vision=None):
    sightings = []
    if ALLIGATOR_HISTORY_PATH.exists():
        try:
            stored = json.loads(ALLIGATOR_HISTORY_PATH.read_text(encoding="utf-8-sig"))
            sightings.extend(stored.get("sightings", []))
        except (OSError, json.JSONDecodeError):
            pass
    if previous_vision:
        sightings.extend(sightings_from_vision(previous_vision))
    return sightings


def update_alligator_history(sightings, current_vision):
    sightings.extend(sightings_from_vision(current_vision))

    unique = {}
    for item in sightings:
        key = (
            item.get("capture_time_ct"),
            item.get("camera_id"),
            item.get("location_in_frame"),
        )
        if parse_capture_time(item.get("capture_time_ct")):
            unique[key] = item

    ordered = sorted(
        unique.values(),
        key=lambda item: parse_capture_time(item["capture_time_ct"]),
    )
    ALLIGATOR_HISTORY_PATH.write_text(
        json.dumps({"sightings": ordered}, indent=2),
        encoding="utf-8",
    )
    return ordered


def build_recent_alligator_status(sightings, capture_time_ct):
    reference = parse_capture_time(capture_time_ct) or datetime.now(TZ)
    recent_cutoff = reference - timedelta(days=ALLIGATOR_RECENT_DAYS)

    today = []
    recent = []
    for item in sightings:
        seen_at = parse_capture_time(item.get("capture_time_ct"))
        if not seen_at or seen_at > reference + timedelta(minutes=1):
            continue
        if seen_at.date() == reference.date():
            today.append(item)
        if seen_at >= recent_cutoff:
            recent.append(item)

    today.sort(key=lambda item: parse_capture_time(item["capture_time_ct"]), reverse=True)
    recent.sort(key=lambda item: parse_capture_time(item["capture_time_ct"]), reverse=True)
    most_recent = recent[0] if recent else None

    if today:
        headline = (
            f"ALLIGATOR SEEN TODAY at {today[0]['camera_label']}, "
            f"{today[0]['location_in_frame']}."
        )
    elif most_recent:
        headline = (
            f"No alligator seen today; most recent confirmed sighting was "
            f"{most_recent['capture_time_ct']} at {most_recent['camera_label']}, "
            f"{most_recent['location_in_frame']}."
        )
    else:
        headline = (
            f"No confirmed alligator seen today or in the last "
            f"{ALLIGATOR_RECENT_DAYS} days of retained analysis history."
        )

    return {
        "headline": headline,
        "seen_today": bool(today),
        "seen_recently": bool(recent),
        "recent_window_days": ALLIGATOR_RECENT_DAYS,
        "most_recent_detection": most_recent,
        "detections_today": today,
        "detections_recent": recent,
        "history_source": "retained confirmed detections from available vision analyses",
    }


def main():

    if not STATUS_PATH.exists():
        raise SystemExit(
            f"Missing: {STATUS_PATH}"
        )

    if not BURST_STATUS_PATH.exists():
        raise SystemExit(
            f"Missing: {BURST_STATUS_PATH}"
        )

    if not RUBRIC_PATH.exists():
        raise SystemExit(
            f"Missing: {RUBRIC_PATH}"
        )

    status = json.loads(
        STATUS_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    burst_status = json.loads(
        BURST_STATUS_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    rubric = json.loads(
        RUBRIC_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    previous_vision = None
    if VISION_PATH.exists():
        try:
            previous_vision = json.loads(
                VISION_PATH.read_text(encoding="utf-8-sig")
            )
        except (OSError, json.JSONDecodeError):
            pass

    output = {
        "capture_time_ct":
            status.get("capture_time_ct"),

        "dawn_ct":
            status.get("dawn_ct"),

        "window_start_ct":
            status.get("window_start_ct"),

        "window_end_ct":
            status.get("window_end_ct"),

        "analysis_model":
            "gpt-5.6-luna",

        "rubric_version":
            rubric.get("rubric_version"),

        "analysis_type":
            "three_frame_temporal_burst",

        "burst_target_spacing_seconds":
            burst_status.get(
                "target_spacing_seconds"
            ),

        "cameras": {},

        "cross_camera": {}
    }

    for camera_id, camera_label in CAMERAS:

        burst_cam = (
            burst_status.get(
                "cameras",
                {}
            ).get(
                camera_id,
                {}
            )
        )

        if burst_cam.get("ok") is not True:
            output["cameras"][camera_id] = {
                "camera_id": camera_id,
                "camera_label": camera_label,
                "status": "burst_not_ok"
            }

            print(
                f"SKIPPED: {camera_id}"
            )

            continue

        image_paths = [
            BURST_DIR /
            f"{camera_id}_{i}.jpg"
            for i in range(1, 4)
        ]

        missing = [
            str(p)
            for p in image_paths
            if not p.exists()
        ]

        if missing:
            output["cameras"][camera_id] = {
                "camera_id": camera_id,
                "camera_label": camera_label,
                "status": "burst_image_missing",
                "missing": missing
            }

            print(
                f"SKIPPED: {camera_id} "
                "missing burst image"
            )

            continue

        print(
            f"ANALYZING 3-FRAME BURST: "
            f"{camera_id}"
        )

        analysis = analyze_burst(
            camera_id,
            camera_label,
            image_paths,
            burst_cam.get(
                "shots",
                []
            ),
            rubric
        )

        analysis["status"] = "ok"

        output["cameras"][
            camera_id
        ] = analysis

    print()
    print(
        "ANALYZING CROSS-CAMERA "
        "TEMPORAL STATE"
    )

    output["cross_camera"] = (
        cross_camera_analysis(
            output["cameras"],
            rubric
        )
    )

    output["cross_camera"]["alligator_alert"] = build_alligator_alert(
        output["cameras"],
        output["capture_time_ct"],
    )

    sightings = update_alligator_history(
        load_alligator_history(previous_vision),
        output,
    )
    recent_status = build_recent_alligator_status(
        sightings,
        output["capture_time_ct"],
    )
    output["cross_camera"]["alligator_recent_status"] = recent_status
    output["cross_camera"]["alligator_summary"] = recent_status["headline"]

    VISION_PATH.write_text(
        json.dumps(
            output,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print(
        f"WROTE: {VISION_PATH}"
    )

    print(
        "ANALYSIS TYPE: "
        "three_frame_temporal_burst"
    )

    print(
        f"RUBRIC VERSION: "
        f"{rubric.get('rubric_version')}"
    )


if __name__ == "__main__":
    main()

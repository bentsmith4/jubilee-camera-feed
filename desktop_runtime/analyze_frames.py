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
RUNTIME_VERSION = "2026-09-18-cache-compact-synthesis-v2"


def api_response(stage, **kwargs):
    """Record token usage locally without changing request or failure behavior."""
    require_season()
    started = time.monotonic()
    response = None
    try:
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
                "cached_input_tokens": getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None),
                "reasoning_output_tokens": getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None),
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


def camera_stable_prompt(rubric):
    """Stable, cacheable vision instructions shared by every camera."""
    return f"""
You analyze THREE sequential images from one Mobile Bay Jubilee monitoring camera.
The images are presented in chronological order. Use the supplied shot timestamps
and preserve actual versus nominal/estimated timing provenance.

Use the camera-specific role only as viewing-context guidance. Do not invent
biological detail that cannot be resolved in the images.

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

PRIORITY OBSERVATIONS:
- shrimp popping, flicking, repeated rings, or surface concentration
- fish jumping, repeated surface breaks, gulping, smoking, or boils
- surface-swimming crabs or crabs climbing structures
- flounder, eels, rays, or other bottom fauna displaced upward
- dense shoreline/structure accumulation or offshore abnormal aggregation
- repeated bird feeding strikes as supporting evidence
- people, flashlights, clustered searching, or seafood collection only as weak
  descriptive human-sensor evidence

CONFOUNDERS TO DISTINGUISH:
rain, normal wavelets, reflections, glare, insects, floating debris, ordinary
mullet jumps, boat wake, moving boats, artificial light attraction, logs,
branches, birds, wave crests, and camera artifacts.

ALLIGATOR SAFETY CHECK:
Inspect every frame for an American alligator. Mark "clear" only when
recognizable alligator anatomy is visible (head/eyes/snout profile, body/scutes,
or tail), not merely a dark shape or wake. Use "possible" for unresolved
candidates. Compare all three frames for persistence or biologically plausible
motion. "near_people" means both are visibly in the same local area; do not
infer distance the image cannot show.

RULES:
- Multi-frame persistence is more credible than a one-frame feature.
- Biologically plausible motion is more credible than a stationary reflection.
- Do not diagnose dissolved oxygen.
- Darkness or occlusion means unknown, not absence.
- Human observations are anonymous only. Never identify or track people.
- human_sensor_score is descriptive only: 0=no visible search, 0.5=possible
  search, 1=clear persistent clustered search; otherwise null.
- Keep all free-text strings extremely short: frame summaries <=8 words,
  location descriptions <=8 words, temporal_summary <=18 words.
- Return ONLY valid JSON and no markdown.

Use exactly these fields and enum vocabularies:
{{
  "visibility":"poor|fair|good",
  "detectability":"low|moderate|high",
  "water_surface":"flat|slight_ripple|moderate_chop|choppy|unclear",
  "rain_surface_interference":"none|possible|strong|unclear",
  "wake_interference":"none|possible|strong|unclear",
  "fish_surface_activity":"none_visible|isolated|possible_abnormal|clear_abnormal|dense|unclear",
  "fish_jump_activity":"none_visible|isolated|multiple|dense|unclear",
  "fish_gulping_or_smoking":"none_visible|possible|clear|widespread|unclear",
  "shrimp_surface_popping":"none_visible|possible|multiple|dense|unclear",
  "shrimp_surface_concentration":"none_visible|possible|clear|dense|unclear",
  "crab_surface_swimming":"none_visible|possible|clear|multiple|unclear",
  "crab_climbing_structure":"none_visible|possible|clear|multiple|unclear",
  "flounder_or_flatfish_shallow":"none_visible|possible|clear|multiple|unclear",
  "eel_displacement":"none_visible|possible|clear|multiple|unclear",
  "stingray_or_other_bottom_fauna_displacement":"none_visible|possible|clear|multiple|unclear",
  "shoreline_or_structure_accumulation":"none_visible|possible|clear|dense|unclear",
  "offshore_bottom_fauna_surface_aggregation":"none_visible|possible|clear|dense|unclear",
  "bird_feeding_activity":"none_visible|possible|active|dense_active|unclear",
  "people_present":"none_visible|possible|clear|unknown",
  "flashlight_activity":"none_visible|possible|clear|unknown",
  "motion_pattern":"none_visible|stationary|walking|searching|unknown",
  "clustered_search_behavior":"none_visible|possible|clear|unknown",
  "temporal_persistence":"none_visible|one_frame|multiple_frames|unknown",
  "human_sensor_score":null,
  "human_sensor_confidence":0.0,
  "human_sensor_detectability":"good|limited|poor|unknown",
  "people_collecting_seafood":"none_visible|possible|clear|unclear",
  "animal_lethargy_or_abnormal_motion":"none_visible|possible|clear|widespread|unclear",
  "alligator_frame_detections":[
    {{"frame":1,"visible":"none|possible|clear|unclear","count_estimate":0,"behavior":"none|swimming|stationary|feeding_or_striking|near_people|other|unclear","location_in_frame":"short description or none","confidence":0.0}},
    {{"frame":2,"visible":"none|possible|clear|unclear","count_estimate":0,"behavior":"none|swimming|stationary|feeding_or_striking|near_people|other|unclear","location_in_frame":"short description or none","confidence":0.0}},
    {{"frame":3,"visible":"none|possible|clear|unclear","count_estimate":0,"behavior":"none|swimming|stationary|feeding_or_striking|near_people|other|unclear","location_in_frame":"short description or none","confidence":0.0}}
  ],
  "alligator_visible":"none|possible|clear|unclear",
  "alligator_count_estimate":0,
  "alligator_behavior":"none|swimming|stationary|feeding_or_striking|near_people|other|unclear",
  "alligator_location_in_frame":"short description or none",
  "alligator_temporal_change":"none|stationary|moving|appeared|disappeared|behavior_changed|unclear",
  "alligator_confidence":0.0,
  "artificial_light_confounding":"none|possible|strong|unclear",
  "repeated_surface_activity":"none_visible|possible|clear|unclear",
  "activity_changed_across_frames":"no|possible|yes|unclear",
  "likely_temporal_artifact":"none|rain|wake|reflection|camera|other|unclear",
  "temporal_jubilee_signal":"none|weak_possible|moderate|strong|unclear",
  "overall_jubilee_visual_signal":"none|weak_possible|moderate|strong|unclear",
  "frame_1_summary":"short description",
  "frame_2_summary":"short description",
  "frame_3_summary":"short description",
  "temporal_summary":"short description",
  "confidence":0.0
}}
"""


def analyze_burst(
    camera_id,
    camera_label,
    image_paths,
    shot_metadata,
    rubric
):
    camera_guidance = (
        rubric.get("camera_role_guidance", {}).get(camera_id, [])
    )
    shot_timing = [
        {
            key: shot[key]
            for key in ("shot", "timestamp_ct", "timing")
            if key in shot
        }
        for shot in shot_metadata
    ]

    stable_prompt = camera_stable_prompt(rubric)
    dynamic_prompt = (
        "CAMERA ID:\n"
        f"{camera_id}\n\n"
        "CAMERA LABEL:\n"
        f"{camera_label}\n\n"
        "CAMERA ROLE:\n"
        f"{json.dumps(camera_guidance, separators=(',', ':'))}\n\n"
        "SHOT TIMING (actual/nominal labels are provenance, not guesses):\n"
        f"{json.dumps(shot_timing, separators=(',', ':'))}\n\n"
        "Analyze FRAME 1, FRAME 2, FRAME 3 in chronological order."
    )

    content = [{"type": "input_text", "text": dynamic_prompt}]
    for path in image_paths:
        content.append(image_content(path))

    cache_key = f"jubilee-camera-v2-{rubric.get('rubric_version', 'unknown')}"
    response = api_response(
        f"camera:{camera_id}",
        model="gpt-5.6-luna",
        prompt_cache_key=cache_key[:64],
        prompt_cache_options={"mode": "explicit", "ttl": "30m"},
        max_output_tokens=1800,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": stable_prompt,
                        "prompt_cache_breakpoint": {"mode": "explicit"}
                    }
                ]
            },
            {"role": "user", "content": content}
        ]
    )

    result = clean_json(response.output_text)

    required_human = {
        "people_present", "flashlight_activity", "motion_pattern",
        "clustered_search_behavior", "temporal_persistence",
        "human_sensor_score", "human_sensor_confidence",
        "human_sensor_detectability"
    }
    if not required_human.issubset(result):
        raise ValueError("Missing human-observation schema fields")

    score = result["human_sensor_score"]
    if (
        score is not None
        and (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not 0 <= score <= 1
        )
    ):
        raise ValueError("Invalid descriptive human score")

    if result["human_sensor_detectability"] in {"poor", "unknown"}:
        result["human_sensor_score"] = None

    result["human_sensor_schema_version"] = "1.0-descriptive-unvalidated"
    result["camera_id"] = camera_id
    result["camera_label"] = camera_label
    result["burst_shots"] = shot_metadata
    result["burst_frame_count"] = len(image_paths)
    return result


SYNTHESIS_FIELDS = (
    "camera_id", "camera_label", "visibility", "detectability", "water_surface",
    "rain_surface_interference", "wake_interference",
    "fish_surface_activity", "fish_jump_activity", "fish_gulping_or_smoking",
    "shrimp_surface_popping", "shrimp_surface_concentration",
    "crab_surface_swimming", "crab_climbing_structure",
    "flounder_or_flatfish_shallow", "eel_displacement",
    "stingray_or_other_bottom_fauna_displacement",
    "shoreline_or_structure_accumulation",
    "offshore_bottom_fauna_surface_aggregation",
    "bird_feeding_activity", "people_present", "flashlight_activity",
    "motion_pattern", "clustered_search_behavior", "temporal_persistence",
    "human_sensor_score", "people_collecting_seafood",
    "animal_lethargy_or_abnormal_motion", "alligator_visible",
    "alligator_behavior", "alligator_confidence",
    "artificial_light_confounding", "repeated_surface_activity",
    "activity_changed_across_frames", "likely_temporal_artifact",
    "temporal_jubilee_signal", "overall_jubilee_visual_signal",
    "confidence", "burst_shots"
)


def compact_analysis_for_synthesis(analysis):
    """Keep only fields that can affect cross-camera judgment."""
    return {
        key: analysis.get(key)
        for key in SYNTHESIS_FIELDS
        if key in analysis
    }


def cross_camera_stable_prompt():
    return """
Synthesize Mobile Bay Jubilee camera analyses. Each camera result came from
THREE sequential frames with a nominal ten-second target spacing. Use retained
burst_shots timestamps and timing labels. Different cameras may have different
capture times; do not assume simultaneous observations.

Spatial dependence:
- Montrose Pier Bird, Montrose Pier Boat, and Montrose Shoreline are one site.
- Point Clear E2 Bay Mouth and E2 Back Deck are one location.
- Point Clear E3 is about 50 feet from E2.
These are correlated views, not fully independent confirmations.

Biological priority:
1 shrimp popping / surface concentration
2 fish gulping or smoking
3 multiple surface-swimming crabs
4 crabs climbing structures
5 displaced bottom fauna
6 dense shoreline/offshore abnormal aggregation
7 repeated abnormal behavior across frames
8 birds/people only as supporting evidence

Do not invent evidence. Darkness, poor detectability, missing cameras, or
unclear observations increase uncertainty; they are not biological negatives.
Keep free-text fields <=12 words and important_confounders to at most 3 items.
Return ONLY valid JSON:
{
  "overall_visual_jubilee_signal":"none|weak_possible|moderate|strong|unclear",
  "montrose_visual_signal":"none|weak_possible|moderate|strong|unclear",
  "point_clear_visual_signal":"none|weak_possible|moderate|strong|unclear",
  "temporal_confirmation":"none|limited|moderate|strong",
  "highest_value_observation":"short string",
  "highest_value_temporal_change":"short string",
  "important_confounders":["short strings"],
  "spatial_confirmation":"none|limited|moderate|strong",
  "recommendation_for_next_burst":"short string",
  "alligator_summary":"short factual summary",
  "confidence":0.0
}
"""


def cross_camera_analysis(analyses, rubric):
    compact = {
        camera_id: compact_analysis_for_synthesis(analysis)
        for camera_id, analysis in analyses.items()
        if analysis.get("status") == "ok"
    }

    dynamic_prompt = (
        "CAMERA RESULTS:\n"
        + json.dumps(compact, separators=(",", ":"))
    )
    response = api_response(
        "cross_camera",
        model="gpt-5.6-luna",
        prompt_cache_key="jubilee-cross-camera-v2",
        prompt_cache_options={"mode": "explicit", "ttl": "30m"},
        max_output_tokens=800,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": cross_camera_stable_prompt(),
                        "prompt_cache_breakpoint": {"mode": "explicit"}
                    }
                ]
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": dynamic_prompt}]
            }
        ]
    )
    result = clean_json(response.output_text)
    result["synthesis_mode"] = "model"
    return result


BIOLOGICAL_BASELINES = {
    "fish_surface_activity": {"none_visible"},
    "fish_jump_activity": {"none_visible"},
    "fish_gulping_or_smoking": {"none_visible"},
    "shrimp_surface_popping": {"none_visible"},
    "shrimp_surface_concentration": {"none_visible"},
    "crab_surface_swimming": {"none_visible"},
    "crab_climbing_structure": {"none_visible"},
    "flounder_or_flatfish_shallow": {"none_visible"},
    "eel_displacement": {"none_visible"},
    "stingray_or_other_bottom_fauna_displacement": {"none_visible"},
    "shoreline_or_structure_accumulation": {"none_visible"},
    "offshore_bottom_fauna_surface_aggregation": {"none_visible"},
    "bird_feeding_activity": {"none_visible"},
    "people_collecting_seafood": {"none_visible"},
    "animal_lethargy_or_abnormal_motion": {"none_visible"},
    "repeated_surface_activity": {"none_visible"},
}


def requires_cross_camera_model(analyses):
    """Skip synthesis only for a complete, high-detectability, clearly quiet burst."""
    ok = [a for a in analyses.values() if a.get("status") == "ok"]
    if len(ok) != len(CAMERAS):
        return True

    for analysis in ok:
        if analysis.get("visibility") not in {"fair", "good"}:
            return True
        if analysis.get("detectability") not in {"moderate", "high"}:
            return True
        if analysis.get("overall_jubilee_visual_signal") != "none":
            return True
        if analysis.get("temporal_jubilee_signal") != "none":
            return True
        if analysis.get("alligator_visible") != "none":
            return True
        if analysis.get("flashlight_activity") not in {"none_visible", None}:
            return True
        if analysis.get("clustered_search_behavior") not in {"none_visible", None}:
            return True
        score = analysis.get("human_sensor_score")
        if score not in {None, 0, 0.0}:
            return True
        for field, baseline in BIOLOGICAL_BASELINES.items():
            if analysis.get(field) not in baseline:
                return True
    return False


def quiet_cross_camera_analysis(analyses):
    """Deterministic result for a complete burst with no positive/ambiguous signals."""
    confidences = []
    for analysis in analyses.values():
        if analysis.get("status") != "ok":
            continue
        try:
            confidences.append(float(analysis.get("confidence", 0.0) or 0.0))
        except (TypeError, ValueError):
            pass

    confidence = min(confidences) if confidences else 0.0
    return {
        "overall_visual_jubilee_signal": "none",
        "montrose_visual_signal": "none",
        "point_clear_visual_signal": "none",
        "temporal_confirmation": "none",
        "highest_value_observation": "No abnormal biological activity visible.",
        "highest_value_temporal_change": "No persistent abnormal change visible.",
        "important_confounders": [],
        "spatial_confirmation": "none",
        "recommendation_for_next_burst": "Continue scheduled burst cadence.",
        "alligator_summary": "No clear alligator detected.",
        "confidence": round(confidence, 3),
        "synthesis_mode": "deterministic_quiet"
    }


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
        "runtime_version": RUNTIME_VERSION,
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

    if requires_cross_camera_model(output["cameras"]):
        output["cross_camera"] = cross_camera_analysis(
            output["cameras"],
            rubric
        )
    else:
        print("CROSS-CAMERA MODEL SKIPPED: complete quiet burst")
        output["cross_camera"] = quiet_cross_camera_analysis(
            output["cameras"]
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

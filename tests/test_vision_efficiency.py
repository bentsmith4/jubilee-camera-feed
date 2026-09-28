import copy
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_runtime"))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"openai": types.SimpleNamespace(OpenAI=lambda: None),
                                  "camera_policy": types.SimpleNamespace(CAMERAS=[])}):
        spec.loader.exec_module(module)
    return module

NEW = load("efficient_analyzer", ROOT / "desktop_runtime/analyze_frames.py")

class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        season_patch = patch.object(NEW, "require_season", return_value=None)
        season_patch.start()
        self.addCleanup(season_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        NEW.API_USAGE_PATH = Path(self.tmp.name) / "api_usage.jsonl"
        self.payload = {
            "people_present": "unknown", "flashlight_activity": "unknown",
            "motion_pattern": "unknown", "clustered_search_behavior": "unknown",
            "temporal_persistence": "unknown", "human_sensor_score": None,
            "human_sensor_confidence": 0, "human_sensor_detectability": "poor",
        }
        self.response = types.SimpleNamespace(
            output_text=json.dumps(self.payload), status="completed",
            id="response-test", _request_id="request-test", model="gpt-5.6-luna",
            usage=types.SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
        )
        NEW.client = types.SimpleNamespace(
            responses=types.SimpleNamespace(create=Mock(return_value=self.response))
        )

    def test_call_and_result_unchanged(self):
        self.assertIs(
            NEW.api_response("camera:test", model="gpt-5.6-luna", input="PRIVATE"),
            self.response,
        )
        NEW.client.responses.create.assert_called_once_with(
            model="gpt-5.6-luna", input="PRIVATE"
        )
        raw = NEW.API_USAGE_PATH.read_text()
        record = json.loads(raw)
        self.assertEqual(record["total_tokens"], 120)
        self.assertEqual(record["stage"], "camera:test")
        self.assertNotIn("PRIVATE", raw)
        self.assertNotIn("people_present", raw)

    def test_api_failure_preserved(self):
        error = RuntimeError("PRIVATE")
        NEW.client.responses.create.side_effect = error
        with self.assertRaises(RuntimeError) as raised:
            NEW.api_response("camera:test", model="gpt-5.6-luna", input="PRIVATE")
        self.assertIs(raised.exception, error)
        raw = NEW.API_USAGE_PATH.read_text()
        self.assertEqual(json.loads(raw)["status"], "request_failed")
        self.assertNotIn("PRIVATE", raw)

    def test_log_failure_does_not_break_monitoring(self):
        NEW.API_USAGE_PATH = Path(self.tmp.name) / "missing" / "usage.jsonl"
        self.assertIs(
            NEW.api_response("camera:test", model="gpt-5.6-luna"),
            self.response,
        )

    def test_empty_output_is_visible(self):
        self.response.output_text = ""
        NEW.api_response("camera:test", model="gpt-5.6-luna")
        self.assertFalse(
            json.loads(NEW.API_USAGE_PATH.read_text())["output_text_present"]
        )

    def test_camera_prompt_uses_stable_cached_prefix_and_dynamic_suffix(self):
        shots = [
            {
                "shot": 1,
                "timestamp_ct": "2026-09-08T09:06:06-05:00",
                "timing": "actual_screenshot_time",
            },
            {
                "shot": 2,
                "timestamp_ct": "2026-09-08T09:06:16-05:00",
                "timing": "nominal_estimate",
            },
        ]
        result = NEW.analyze_burst("test", "Test", [], shots, {})
        kwargs = NEW.client.responses.create.call_args.kwargs
        stable = kwargs["input"][0]["content"][0]
        dynamic = kwargs["input"][1]["content"][0]["text"]

        self.assertEqual(
            stable["prompt_cache_breakpoint"], {"mode": "explicit"}
        )
        self.assertEqual(
            kwargs["prompt_cache_options"], {"mode": "explicit", "ttl": "30m"}
        )
        self.assertTrue(kwargs["prompt_cache_key"].startswith("jubilee-camera-v2-"))
        self.assertNotIn("2026-09-08T09:06:06-05:00", stable["text"])
        self.assertIn("2026-09-08T09:06:06-05:00", dynamic)
        self.assertIn("actual_screenshot_time", dynamic)
        self.assertIn("nominal_estimate", dynamic)
        self.assertEqual(result["burst_shots"], shots)

    def test_synthesis_compacts_camera_payload(self):
        analysis = {
            "status": "ok",
            "camera_id": "a",
            "camera_label": "A",
            "overall_jubilee_visual_signal": "none",
            "temporal_jubilee_signal": "none",
            "frame_1_summary": "verbose",
            "frame_2_summary": "verbose",
            "burst_shots": [{"shot": 1}],
        }
        compact = NEW.compact_analysis_for_synthesis(analysis)
        self.assertIn("burst_shots", compact)
        self.assertIn("overall_jubilee_visual_signal", compact)
        self.assertNotIn("frame_1_summary", compact)
        self.assertNotIn("frame_2_summary", compact)

    def test_synthesis_preserves_timing_and_nonsimultaneity(self):
        NEW.cross_camera_analysis({}, {})
        kwargs = NEW.client.responses.create.call_args.kwargs
        stable = kwargs["input"][0]["content"][0]["text"]
        self.assertIn("ten-second", stable)
        self.assertIn("do not assume simultaneous observations", stable)
        self.assertEqual(
            kwargs["prompt_cache_options"], {"mode": "explicit", "ttl": "30m"}
        )

    def test_quiet_complete_burst_skips_cross_camera_model(self):
        quiet = {
            "status": "ok",
            "visibility": "good",
            "detectability": "high",
            "overall_jubilee_visual_signal": "none",
            "temporal_jubilee_signal": "none",
            "alligator_visible": "none",
            "flashlight_activity": "none_visible",
            "clustered_search_behavior": "none_visible",
            "human_sensor_score": None,
            "confidence": 0.9,
        }
        for field in NEW.BIOLOGICAL_BASELINES:
            quiet[field] = "none_visible"

        old_cameras = NEW.CAMERAS
        try:
            NEW.CAMERAS = [("a", "A"), ("b", "B")]
            analyses = {"a": dict(quiet), "b": dict(quiet)}
            self.assertFalse(NEW.requires_cross_camera_model(analyses))
            summary = NEW.quiet_cross_camera_analysis(analyses)
            self.assertEqual(summary["synthesis_mode"], "deterministic_quiet")
            self.assertEqual(summary["overall_visual_jubilee_signal"], "none")
        finally:
            NEW.CAMERAS = old_cameras

    def test_any_ambiguous_signal_keeps_cross_camera_model(self):
        base = {
            "status": "ok",
            "visibility": "good",
            "detectability": "high",
            "overall_jubilee_visual_signal": "none",
            "temporal_jubilee_signal": "none",
            "alligator_visible": "none",
            "flashlight_activity": "none_visible",
            "clustered_search_behavior": "none_visible",
            "human_sensor_score": None,
        }
        for field in NEW.BIOLOGICAL_BASELINES:
            base[field] = "none_visible"
        base["shrimp_surface_popping"] = "possible"

        old_cameras = NEW.CAMERAS
        try:
            NEW.CAMERAS = [("a", "A")]
            self.assertTrue(NEW.requires_cross_camera_model({"a": base}))
        finally:
            NEW.CAMERAS = old_cameras

class SynthesisConsistencyTests(unittest.TestCase):
    def setUp(self):
        fixture = ROOT / "tests/fixtures/vision_quiet_low_detectability_20260927.json"
        self.vision = json.loads(fixture.read_text(encoding="utf-8"))
        self.analyses = self.vision["cameras"]
        self.summary = self.vision["cross_camera"]

    def test_original_quiet_low_detectability_burst_is_guarded_after_model(self):
        self.assertEqual(self.vision["capture_time_ct"],
                         "2026-09-27T19:06:05.402643-05:00")
        original = copy.deepcopy(self.vision)
        self.assertTrue(NEW.requires_cross_camera_model(self.analyses))
        response = types.SimpleNamespace(output_text=json.dumps(self.summary))
        with patch.object(NEW, "api_response", return_value=response) as api:
            result = NEW.cross_camera_analysis(self.analyses, {})
        api.assert_called_once()
        expected = dict(self.summary,
                        overall_visual_jubilee_signal="unclear",
                        point_clear_visual_signal="unclear")
        self.assertEqual(result, expected)
        self.assertEqual(self.vision, original)

    def test_positive_biological_and_supporting_observations_survive_darkness(self):
        rubric = json.loads((ROOT / "vision_rubric.json").read_text())
        cases = [
            (field, value)
            for field in NEW.BIOLOGICAL_BASELINES
            for value in rubric["required_output_fields"].get(
                field, ["none_visible", "possible", "clear", "unclear"]
            )
            if value not in {"none_visible", "unclear"}
        ]
        cases.extend([
            ("flashlight_activity", "possible"),
            ("flashlight_activity", "clear"),
            ("clustered_search_behavior", "possible"),
            ("clustered_search_behavior", "clear"),
            ("motion_pattern", "searching"),
            ("human_sensor_score", 0.5),
            ("human_sensor_score", 1),
        ])
        for field, value in cases:
            with self.subTest(field=field, value=value):
                analyses = copy.deepcopy(self.analyses)
                analyses["pcl_e2_back_deck"][field] = value
                self.assertEqual(
                    NEW.check_synthesis_consistency(self.summary, analyses),
                    self.summary,
                )

    def test_support_is_scoped_to_its_site(self):
        for camera_id, supported, unsupported in (
            ("montrose_pier_bird", "montrose_visual_signal", "point_clear_visual_signal"),
            ("pcl_e2_back_deck", "point_clear_visual_signal", "montrose_visual_signal"),
        ):
            with self.subTest(camera=camera_id):
                analyses = copy.deepcopy(self.analyses)
                analyses[camera_id]["bird_feeding_activity"] = "possible"
                summary = dict(self.summary, montrose_visual_signal="weak_possible")
                result = NEW.check_synthesis_consistency(summary, analyses)
                self.assertEqual(result["overall_visual_jubilee_signal"], "weak_possible")
                self.assertEqual(result[supported], "weak_possible")
                self.assertEqual(result[unsupported], "unclear")

    def test_uncertainty_confounders_and_summary_labels_are_not_support(self):
        for changes in (
            {"people_present": "clear", "motion_pattern": "walking"},
            {"overall_jubilee_visual_signal": "weak_possible",
             "temporal_jubilee_signal": "weak_possible"},
            {"activity_changed_across_frames": "yes"},
            {"fish_surface_activity": "unknown", "flashlight_activity": "unknown"},
            {"fish_surface_activity": None, "human_sensor_score": True},
            {"human_sensor_score": "0.5"},
            {"alligator_visible": "clear", "alligator_confidence": 0.99},
        ):
            with self.subTest(changes=changes):
                analyses = copy.deepcopy(self.analyses)
                analyses["pcl_e2_back_deck"].update(changes)
                result = NEW.check_synthesis_consistency(self.summary, analyses)
                self.assertEqual(result["overall_visual_jubilee_signal"], "unclear")
                self.assertEqual(result["point_clear_visual_signal"], "unclear")

    def test_failed_or_missing_cameras_cannot_supply_support(self):
        for analyses in ({}, {"pcl_e2_back_deck": {
            "status": "burst_not_ok", "shrimp_surface_popping": "possible",
        }}, {"pcl_e2_back_deck": {"status": "ok"}}):
            with self.subTest(analyses=analyses):
                result = NEW.check_synthesis_consistency(self.summary, analyses)
                self.assertEqual(result["overall_visual_jubilee_signal"], "unclear")
                self.assertEqual(result["point_clear_visual_signal"], "unclear")

    def test_other_labels_and_safety_metadata_are_unchanged(self):
        for label in ("none", "unclear", "moderate", "strong"):
            with self.subTest(label=label):
                summary = dict(self.summary,
                               overall_visual_jubilee_signal=label,
                               point_clear_visual_signal=label,
                               alligator_alert={"triggered": True})
                self.assertEqual(
                    NEW.check_synthesis_consistency(summary, self.analyses), summary
                )


if __name__ == "__main__":
    unittest.main()

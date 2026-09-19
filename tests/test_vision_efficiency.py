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

if __name__ == "__main__":
    unittest.main()

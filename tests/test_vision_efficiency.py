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
        NEW.client = types.SimpleNamespace(responses=types.SimpleNamespace(create=Mock(return_value=self.response)))

    def test_call_and_result_unchanged(self):
        self.assertIs(NEW.api_response("camera:test", model="gpt-5.6-luna", input="PRIVATE"), self.response)
        NEW.client.responses.create.assert_called_once_with(model="gpt-5.6-luna", input="PRIVATE")
        raw = NEW.API_USAGE_PATH.read_text()
        record = json.loads(raw)
        self.assertEqual(record["total_tokens"],120)
        self.assertEqual(record["stage"],"camera:test")
        self.assertNotIn("PRIVATE",raw)
        self.assertNotIn("people_present",raw)

    def test_api_failure_preserved(self):
        error = RuntimeError("PRIVATE")
        NEW.client.responses.create.side_effect = error
        with self.assertRaises(RuntimeError) as raised:
            NEW.api_response("camera:test", model="gpt-5.6-luna", input="PRIVATE")
        self.assertIs(raised.exception,error)
        raw = NEW.API_USAGE_PATH.read_text()
        self.assertEqual(json.loads(raw)["status"],"request_failed")
        self.assertNotIn("PRIVATE",raw)

    def test_log_failure_does_not_break_monitoring(self):
        NEW.API_USAGE_PATH = Path(self.tmp.name) / "missing" / "usage.jsonl"
        self.assertIs(NEW.api_response("camera:test", model="gpt-5.6-luna"),self.response)

    def test_empty_output_is_visible(self):
        self.response.output_text = ""
        NEW.api_response("camera:test", model="gpt-5.6-luna")
        self.assertFalse(json.loads(NEW.API_USAGE_PATH.read_text())["output_text_present"])

    def test_camera_prompt_includes_timing_provenance(self):
        shots = [{"shot": 1, "timestamp_ct": "2026-09-08T09:06:06-05:00", "timing": "actual_screenshot_time"},
                 {"shot": 2, "timestamp_ct": "2026-09-08T09:06:16-05:00", "timing": "nominal_estimate"}]
        result = NEW.analyze_burst("test", "Test", [], shots, {})
        prompt = NEW.client.responses.create.call_args.kwargs["input"][0]["content"][0]["text"]
        self.assertIn("2026-09-08T09:06:06-05:00", prompt)
        self.assertIn("actual_screenshot_time", prompt)
        self.assertIn("nominal_estimate", prompt)
        self.assertEqual(result["burst_shots"], shots)

    def test_synthesis_preserves_real_timing_and_nonsimultaneity(self):
        NEW.cross_camera_analysis({}, {})
        prompt = NEW.client.responses.create.call_args.kwargs["input"]
        self.assertNotIn("one second apart", prompt)
        self.assertIn("ten seconds", prompt)
        self.assertIn("do not assume simultaneous observations", prompt)


if __name__ == "__main__":
    unittest.main()

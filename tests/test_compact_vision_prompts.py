import hashlib
import json
import unittest
from test_vision_efficiency import NEW, ROOT

class CompactPromptTests(unittest.TestCase):
    def test_observation_schemas_preserved(self):
        rubric = json.loads((ROOT / "vision_rubric.json").read_text())
        for prompt, expected in (
            (NEW.camera_stable_prompt(rubric), "0637586cb9eb6ae3a37aad4801fc06b462e62494240e21ce54df3f77e36a06e7"),
            (NEW.cross_camera_stable_prompt(), "e092b978ac9f74f35ce59235cf7f5d26de4b09c020be324cb4fea5c56e73eeca"),
        ):
            schema_text = prompt[prompt.rfind("\n{") + 1:].strip()
            schema = json.loads(schema_text)
            self.assertEqual(hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest(), expected)
            self.assertEqual(schema_text, json.dumps(schema, separators=(",", ":")))
            self.assertIn("Return compact JSON", prompt)

    def test_compact_response_preserves_unknown_and_safety(self):
        result = {"fish_surface_activity": "unclear", "people_present": "unknown",
                  "human_sensor_score": None, "alligator_visible": "possible",
                  "alligator_frame_detections": [{"frame": 1, "visible": "possible"}]}
        self.assertEqual(NEW.clean_json(json.dumps(result, separators=(",", ":"))), result)

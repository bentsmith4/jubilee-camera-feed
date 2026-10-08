import unittest
from model_data.analyze_camera_marginal_value import has_signal, score_snapshots, usage_costs

class CameraAuditTests(unittest.TestCase):
    def test_none_is_not_signal(self):
        self.assertFalse(has_signal({"status":"ok","overall_jubilee_visual_signal":"none","fish_surface_activity":"none_visible"}))

    def test_positive_field_is_signal(self):
        self.assertTrue(has_signal({"status":"ok","fish_surface_activity":"present"}))

    def test_unique_signal_within_site(self):
        snap={"cameras":{
          "montrose_pier_bird":{"status":"ok","fish_surface_activity":"present"},
          "montrose_pier_boat":{"status":"ok","fish_surface_activity":"none_visible"},
          "montrose_shoreline":{"status":"ok","fish_surface_activity":"none_visible"},
        }}
        out=score_snapshots([snap])
        self.assertEqual(out["montrose_pier_bird"]["unique_signal"],1)

    def test_usage_join(self):
        groups=[{"date_ct":"2026-10-01","stage":"camera:pcl_e2_back_deck","completed_requests":2,"tokens":{"total_tokens":{"known_sum":200}}}]
        out=usage_costs(groups,"2026-10-01","2026-10-01")
        self.assertEqual(out["cameras"]["pcl_e2_back_deck"]["tokens_per_request"],100)

if __name__=="__main__":
    unittest.main()

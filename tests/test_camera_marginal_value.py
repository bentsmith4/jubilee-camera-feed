import unittest
from model_data.analyze_camera_marginal_value import (
    CAMERAS, SIGNAL_FIELDS, has_signal, observation_state, score_snapshots, usage_costs,
)

def row(**changes):
    result = dict.fromkeys(SIGNAL_FIELDS, "none_visible")
    result.update(status="ok", visibility="good", detectability="moderate")
    result.update(changes)
    return result

class CameraAuditTests(unittest.TestCase):
    def test_complete_negative(self):
        self.assertEqual(observation_state(row()), "NEGATIVE")

    def test_positive_rubric_observations(self):
        for field, value in (("fish_surface_activity", "clear_abnormal"),
                             ("fish_jump_activity", "isolated"),
                             ("bird_feeding_activity", "active"),
                             ("people_present", "clear"),
                             ("overall_jubilee_visual_signal", "strong")):
            with self.subTest(field=field):
                self.assertTrue(has_signal(row(**{field: value})))

    def test_unknown_and_unexpected_values(self):
        for value in ("unknown", "unclear", "not_assessable", "unavailable",
                      "uncertain", "null", "undefined", "", None, False, 0,
                      "invented_positive", {}, []):
            with self.subTest(value=value):
                self.assertEqual(observation_state(row(fish_surface_activity=value)), "UNKNOWN")
                self.assertFalse(has_signal(row(fish_surface_activity=value)))

    def test_possible_labels_are_unconfirmed(self):
        for field, value in (("fish_surface_activity", "possible_abnormal"),
                             ("people_present", "possible"),
                             ("overall_jubilee_visual_signal", "weak_possible")):
            self.assertEqual(observation_state(row(**{field: value})), "UNKNOWN")

    def test_missing_field_is_unknown(self):
        r = row()
        del r["fish_surface_activity"]
        self.assertEqual(observation_state(r), "UNKNOWN")

    def test_positive_can_coexist_with_unknown_field(self):
        self.assertTrue(has_signal(row(fish_surface_activity="unclear", people_present="clear")))

    def test_status_gate(self):
        for status in ("error", "stale", "missing", "unavailable", None):
            self.assertFalse(has_signal(row(status=status, people_present="clear")))

    def test_quality_gate(self):
        for field, values in (("visibility", ("poor", "very_poor", "dark", "unknown", "", None)),
                              ("detectability", ("low", "none", "unknown", "", None))):
            for value in values:
                self.assertEqual(observation_state(row(**{field:value, "people_present":"clear"})), "UNKNOWN")

    def test_missing_quality_is_unknown(self):
        for field in ("visibility", "detectability"):
            r = row(people_present="clear")
            del r[field]
            self.assertFalse(has_signal(r))

    def test_same_site_unique_signal(self):
        cameras = {c:row() for c in CAMERAS}
        cameras[CAMERAS[0]] = row(fish_surface_activity="clear_abnormal")
        cameras[CAMERAS[3]] = row(people_present="clear")
        result = score_snapshots([{"cameras":cameras}])
        self.assertEqual(result[CAMERAS[0]]["unique_signal"], 1)
        self.assertEqual(result[CAMERAS[3]]["unique_signal"], 1)

    def test_unknown_peer_blocks_uniqueness(self):
        for peer in (None, row(status="error"), row(visibility="poor"),
                     row(detectability="low"), row(fish_surface_activity="unknown")):
            cameras={CAMERAS[0]:row(people_present="clear"), CAMERAS[1]:row()}
            if peer is not None:
                cameras[CAMERAS[2]]=peer
            result=score_snapshots([{"cameras":cameras}])[CAMERAS[0]]
            self.assertEqual(result["unique_signal"], 0)
            self.assertEqual(result["unique_signal_unassessable"], 1)
            self.assertEqual(result["site_disagreement"], 1)

    def test_unusable_positive_is_not_comparison(self):
        cameras={CAMERAS[0]:row(), CAMERAS[1]:row(visibility="poor", people_present="clear")}
        result=score_snapshots([{"cameras":cameras}])
        self.assertEqual(result[CAMERAS[0]]["site_disagreement"], 0)
        self.assertEqual(result[CAMERAS[1]]["signal"], 0)
        self.assertEqual(result[CAMERAS[1]]["unknown"], 1)

    def test_shared_positive_not_unique(self):
        cameras={CAMERAS[0]:row(people_present="clear"), CAMERAS[1]:row(people_present="clear")}
        result=score_snapshots([{"cameras":cameras}])[CAMERAS[0]]
        self.assertEqual(result["unique_signal"], 0)
        self.assertEqual(result["unique_signal_unassessable"], 0)

    def test_unknown_not_negative_or_disagreement(self):
        result=score_snapshots([{"cameras":{CAMERAS[0]:row(fish_surface_activity="unknown")}}])
        self.assertEqual(result[CAMERAS[0]]["negative"], 0)
        self.assertEqual(result[CAMERAS[0]]["site_disagreement"], 0)
        self.assertEqual(result[CAMERAS[1]]["missing"], 1)

    def test_usage_join(self):
        groups=[{"date_ct":"2026-10-01","stage":"camera:pcl_e2_back_deck","completed_requests":2,"tokens":{"total_tokens":{"known_sum":200}}}]
        out=usage_costs(groups,"2026-10-01","2026-10-01")
        self.assertEqual(out["cameras"]["pcl_e2_back_deck"]["tokens_per_request"],100)

if __name__=="__main__":
    unittest.main()


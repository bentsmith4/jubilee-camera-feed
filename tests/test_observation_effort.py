import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'model_data' / 'build_observation_effort_snapshot.py'
spec = importlib.util.spec_from_file_location('effort', MODULE_PATH)
effort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(effort)


class ObservationEffortTests(unittest.TestCase):
    def _build_with(self, root, status, vision):
        (root / 'model_data').mkdir(exist_ok=True)
        (root / 'status.json').write_text(json.dumps(status))
        (root / 'vision.json').write_text(json.dumps(vision))
        (root / 'model_data' / 'public_camera_observation_log.json').write_text(json.dumps({'records': []}))
        old_root, old_out = effort.ROOT, effort.OUT
        effort.ROOT = root
        effort.OUT = root / 'model_data' / 'observation_effort_snapshot.json'
        try:
            return effort.build()
        finally:
            effort.ROOT, effort.OUT = old_root, old_out

    def test_dark_montrose_shoreline_never_becomes_clean_negative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            status = {
                'capture_time_ct': '2026-09-06T05:30:00-05:00',
                'window_start_ct': '2026-09-06T04:00:00-05:00',
                'window_end_ct': '2026-09-06T08:00:00-05:00',
                'cameras': {
                    'montrose_shoreline': {'ok': True},
                    'montrose_pier_boat': {'ok': True},
                    'montrose_pier_bird': {'ok': True},
                },
            }
            vision = {
                'cameras': {
                    'montrose_shoreline': {
                        'status': 'ok', 'visibility': 'poor', 'detectability': 'low',
                        'overall_jubilee_visual_signal': 'none', 'temporal_jubilee_signal': 'none'
                    },
                    'montrose_pier_boat': {'status': 'ok'},
                    'montrose_pier_bird': {'status': 'ok'},
                }
            }
            result = self._build_with(root, status, vision)
            montrose = next(x for x in result['cells'] if x['shoreline_cell'] == 'Montrose')
            self.assertEqual(montrose['control_eligibility'], 'UNKNOWN_PRIMARY_CONTACT_VIEW_INADEQUATE')
            self.assertEqual(montrose['negative_evidence_strength'], 'none')

    def test_good_first_light_montrose_can_be_visible_scope_candidate_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            status = {
                'capture_time_ct': '2026-09-06T06:20:00-05:00',
                'window_start_ct': '2026-09-06T04:00:00-05:00',
                'window_end_ct': '2026-09-06T08:00:00-05:00',
                'cameras': {'montrose_shoreline': {'ok': True}}
            }
            vision = {'cameras': {'montrose_shoreline': {
                'status': 'ok', 'visibility': 'good', 'detectability': 'high',
                'overall_jubilee_visual_signal': 'none', 'temporal_jubilee_signal': 'none'
            }}}
            result = self._build_with(root, status, vision)
            montrose = next(x for x in result['cells'] if x['shoreline_cell'] == 'Montrose')
            self.assertEqual(montrose['control_eligibility'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
            self.assertEqual(montrose['negative_evidence_strength'], 'moderate')

    def test_outside_dawn_window_not_eligible(self):
        self.assertFalse(effort.in_window(
            effort.parse_dt('2026-09-06T22:00:00-05:00'),
            effort.parse_dt('2026-09-06T04:00:00-05:00'),
            effort.parse_dt('2026-09-06T08:00:00-05:00')))

    def test_ledger_appends_only_once_per_dawn_capture(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / 'ledger.jsonl'
            output = {
                'generated_from_capture_time_ct': '2026-09-06T06:20:00-05:00',
                'cycle_in_target_predawn_dawn_window': True,
                'cells': []
            }
            first = effort.append_if_target_window(output, ledger)
            second = effort.append_if_target_window(output, ledger)
            self.assertTrue(first['appended'])
            self.assertFalse(second['appended'])
            self.assertEqual(second['reason'], 'duplicate_capture_id')
            self.assertEqual(len(ledger.read_text().splitlines()), 1)

    def test_ledger_does_not_append_night_cycle(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / 'ledger.jsonl'
            output = {
                'generated_from_capture_time_ct': '2026-09-06T22:20:00-05:00',
                'cycle_in_target_predawn_dawn_window': False,
                'cells': []
            }
            result = effort.append_if_target_window(output, ledger)
            self.assertFalse(result['appended'])
            self.assertFalse(ledger.exists())


if __name__ == '__main__':
    unittest.main()

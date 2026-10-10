"""Offline outage matrix; no real weather, camera, API or production writes."""
import copy
from datetime import datetime, timedelta
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_vision_efficiency as vision_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'storm_effort', ROOT / 'model_data/build_observation_effort_snapshot.py')
effort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(effort)
IDS = tuple(cid for cameras in effort.CELL_CAMERAS.values() for cid in cameras)
T0 = datetime.fromisoformat('2026-10-07T06:52:00-05:00')
NOW = T0 + timedelta(minutes=3)


class SevereWeatherObservationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'model_data').mkdir()
        self.raw = b'\xff\xd8offline-fixture\xff\xd9'
        self.status = dict(capture_time_ct=T0.isoformat(),
                           window_start_ct=(T0-timedelta(hours=2)).isoformat(),
                           window_end_ct=(T0+timedelta(hours=2)).isoformat(), cameras={})
        self.burst = dict(capture_time_ct=T0.isoformat(), cameras={})
        self.vision = dict(capture_time_ct=T0.isoformat(), cameras={})
        shots = [dict(timestamp_ct=(T0+timedelta(seconds=s)).isoformat())
                 for s in (0, 10, 20)]
        for cid in IDS:
            (self.root / (cid+'.jpg')).write_bytes(self.raw)
            self.status['cameras'][cid] = dict(ok=True,
                timestamp_ct=shots[-1]['timestamp_ct'], bytes=len(self.raw))
            self.burst['cameras'][cid] = dict(ok=True, shots=copy.deepcopy(shots))
            self.vision['cameras'][cid] = dict(status='ok', visibility='good',
                detectability='high', overall_jubilee_visual_signal='none',
                temporal_jubilee_signal='none', burst_frame_count=3,
                burst_shots=copy.deepcopy(shots))

    def build(self, status=None, burst=None, vision=None, now=NOW):
        for name, doc in (('status', status or self.status),
                          ('burst_status', burst or self.burst),
                          ('vision', vision or self.vision)):
            (self.root / (name+'.json')).write_text(json.dumps(doc))
        with patch.object(effort, 'ROOT', self.root), patch.object(
                effort, 'OUT', self.root / 'model_data/effort.json'):
            result = effort.build(now)
        self.assertEqual(result['clean_training_negative_count'], 0)
        self.assertEqual(result['production_action'], 'NO_CHANGE')
        point_clear = result['cells'][1]
        self.assertEqual(point_clear['negative_evidence_strength'], 'none')
        self.assertNotEqual(point_clear['control_eligibility'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
        return result

    def assert_unknown_primary(self, result):
        montrose = result['cells'][0]
        self.assertEqual(montrose['control_eligibility'], 'UNKNOWN_PRIMARY_CONTACT_VIEW_INADEQUATE')
        self.assertEqual(montrose['negative_evidence_strength'], 'none')

    def test_all_64_partial_and_complete_outage_combinations(self):
        """Retained old quiet pixels/vision cannot rescue a failed capture."""
        for mask in itertools.product((False, True), repeat=6):
            failed = {cid for cid, outage in zip(IDS, mask) if outage}
            with self.subTest(failed=sorted(failed)):
                status, burst = copy.deepcopy(self.status), copy.deepcopy(self.burst)
                for cid in failed:
                    status['cameras'][cid]['ok'] = False
                    burst['cameras'][cid]['ok'] = False
                result = self.build(status=status, burst=burst)
                rows = {r['camera_id']: r for cell in result['cells'] for r in cell['camera_rows']}
                for cid in IDS:
                    self.assertEqual(rows[cid]['capture_ok'], cid not in failed)
                for cell in result['cells']:
                    self.assertEqual(cell['private_camera_fresh_or_ok_count'],
                        sum(cid not in failed for cid in effort.CELL_CAMERAS[cell['shoreline_cell']]))
                if 'montrose_shoreline' in failed:
                    self.assert_unknown_primary(result)
                else:
                    self.assertEqual(result['cells'][0]['control_eligibility'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')

    def test_missing_products_and_stale_complete_burst_never_create_control(self):
        for missing in ('status', 'burst_status', 'vision', 'all'):
            with self.subTest(missing=missing):
                self.build()
                for name in ('status', 'burst_status', 'vision'):
                    if missing in (name, 'all'):
                        (self.root / (name+'.json')).unlink()
                with patch.object(effort, 'ROOT', self.root), patch.object(
                        effort, 'OUT', self.root / 'model_data/effort.json'):
                    result = effort.build(NOW)
                self.assertEqual(result['clean_training_negative_count'], 0)
                self.assertTrue(all(c['negative_evidence_strength'] == 'none' for c in result['cells']))
                self.assertTrue(all(not r['capture_ok'] for c in result['cells'] for r in c['camera_rows']))
        self.assert_unknown_primary(self.build(now=NOW+timedelta(hours=2)))

    def test_primary_feed_unusable_despite_retained_quiet_classification(self):
        for defect in ('missing_camera', 'missing_image', 'truncated_image',
                       'two_frames', 'vision_cycle_mismatch', 'stale_camera',
                       'poor_visibility', 'low_detectability', 'unknown_signal'):
            with self.subTest(defect=defect):
                status, burst, vision = map(copy.deepcopy, (self.status, self.burst, self.vision))
                cid = 'montrose_shoreline'
                image = self.root / (cid+'.jpg')
                image.write_bytes(self.raw)
                if defect == 'missing_camera':
                    for doc in (status, burst, vision):
                        del doc['cameras'][cid]
                elif defect == 'missing_image': image.unlink()
                elif defect == 'truncated_image': image.write_bytes(b'\xff\xd8broken')
                elif defect == 'two_frames': burst['cameras'][cid]['shots'].pop()
                elif defect == 'vision_cycle_mismatch': vision['capture_time_ct'] = (T0-timedelta(minutes=20)).isoformat()
                elif defect == 'stale_camera': status['cameras'][cid]['timestamp_ct'] = (T0-timedelta(hours=2)).isoformat()
                elif defect == 'poor_visibility': vision['cameras'][cid]['visibility'] = 'poor'
                elif defect == 'low_detectability': vision['cameras'][cid]['detectability'] = 'low'
                else: vision['cameras'][cid]['overall_jubilee_visual_signal'] = 'unknown'
                result = self.build(status, burst, vision)
                self.assertEqual(result['cells'][0]['negative_evidence_strength'], 'none')
                self.assertNotEqual(result['cells'][0]['control_eligibility'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')


class SevereWeatherVisionTests(unittest.TestCase):
    def test_failed_or_missing_images_skip_camera_analysis_and_continue_healthy_feeds(self):
        analyzer = vision_fixture.NEW
        for failure in ('capture_failed', 'missing_image', 'all_failed'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                burst = dict(capture_time_ct=T0.isoformat(), cameras={})
                failed = set(IDS) if failure == 'all_failed' else {'montrose_shoreline'}
                for cid in IDS:
                    burst['cameras'][cid] = dict(ok=cid not in failed or failure == 'missing_image', shots=[])
                    for i in (1, 2, 3):
                        if failure == 'missing_image' and cid in failed and i == 2:
                            continue
                        (root / f'{cid}_{i}.jpg').write_bytes(b'fixture')
                (root / 'status.json').write_text(json.dumps(dict(capture_time_ct=T0.isoformat())))
                (root / 'burst_status.json').write_text(json.dumps(burst))
                (root / 'rubric.json').write_text('{}')
                with patch.multiple(analyzer, STATUS_PATH=root / 'status.json',
                        BURST_STATUS_PATH=root / 'burst_status.json', BURST_DIR=root,
                        RUBRIC_PATH=root / 'rubric.json', VISION_PATH=root / 'vision.json',
                        CAMERAS=[(cid, cid) for cid in IDS]), \
                     patch.object(analyzer, 'analyze_burst', side_effect=lambda *a: {'camera_id': a[0]}) as analyze, \
                     patch.object(analyzer, 'cross_camera_analysis', return_value={'overall_visual_jubilee_signal': 'unclear'}) as cross, \
                     patch.object(analyzer, 'quiet_cross_camera_analysis') as quiet, \
                     patch.object(analyzer, 'load_alligator_history', return_value=[]), \
                     patch.object(analyzer, 'update_alligator_history', return_value=[]):
                    analyzer.main()
                output = json.loads((root / 'vision.json').read_text())
                self.assertEqual({c.args[0] for c in analyze.call_args_list}, set(IDS)-failed)
                cross.assert_called_once()
                quiet.assert_not_called()
                for cid in IDS:
                    row = output['cameras'][cid]
                    if cid in failed:
                        self.assertEqual(row['status'], 'burst_image_missing' if failure == 'missing_image' else 'burst_not_ok')
                        self.assertNotIn('overall_jubilee_visual_signal', row)
                        self.assertNotIn('temporal_jubilee_signal', row)
                    else:
                        self.assertEqual(row['status'], 'ok')


if __name__ == '__main__':
    unittest.main()

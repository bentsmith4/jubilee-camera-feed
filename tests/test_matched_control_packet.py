"""Prospective evidence cannot manufacture a clean negative or a match."""
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'model_data'))
from collect_matched_control_packet import collect, METADATA, CONTEXT
from build_observation_effort_snapshot import parse_dt


class MatchedControlPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base/'repo'
        self.repo.mkdir()
        for name in (*METADATA, *CONTEXT, 'montrose_shoreline.jpg'):
            source = ROOT/name
            if source.is_file():
                target = self.repo/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'test')
        self.commit()
        self.capture = parse_dt(json.loads((self.repo/'status.json').read_text())['capture_time_ct'])

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def update(self, name, mutate):
        path = self.repo/name
        doc = json.loads(path.read_text())
        mutate(doc)
        path.write_text(json.dumps(doc))

    def test_exact_bytes_times_provenance_and_no_promotion(self):
        p = collect(self.repo, self.base/'packet', self.capture+timedelta(minutes=5))
        self.assertEqual(p['source_commit'], self.git('rev-parse', 'HEAD'))
        for name, digest in p['retained_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((self.repo/name).read_bytes()).hexdigest())
            self.assertEqual((self.base/'packet'/name).read_bytes(), (self.repo/name).read_bytes())
        burst = json.loads((self.repo/'burst_status.json').read_text())
        self.assertEqual([s['timestamp_ct'] for s in p['primary_shots']],
                         [s['timestamp_ct'] for s in burst['cameras']['montrose_shoreline']['shots']])
        self.assertFalse(p['tier_a_verified'])
        self.assertEqual(p['biological_event_label'], 'unknown')
        self.assertEqual(p['whole_morning_outcome'], 'UNKNOWN')
        self.assertEqual(p['clean_training_negative_count'], 0)
        self.assertFalse(p['search_absence_is_negative'])
        self.assertTrue(all(v['status'] == 'UNRESOLVED' for v in p['matching_dimensions'].values()))
        self.assertEqual(p['existing_burst_archive']['readback_status'], 'NOT_VERIFIED')
        self.assertFalse(p['existing_burst_archive']['all_three_frames_retained_in_packet'])
        with self.assertRaises(ValueError):
            collect(self.repo, self.base/'packet', self.capture)

    def qualify(self):
        def status(doc):
            doc['window_start_ct'] = (self.capture-timedelta(hours=2)).isoformat()
            doc['window_end_ct'] = (self.capture+timedelta(hours=2)).isoformat()
        def vision(doc):
            v = doc['cameras']['montrose_shoreline']
            v.update(visibility='good', detectability='high', status='ok',
                     overall_jubilee_visual_signal='none', temporal_jubilee_signal='none')
        self.update('status.json', status)
        self.update('vision.json', vision)
        self.commit()

    def test_visibility_integrity_and_event_gates(self):
        self.qualify()
        p = collect(self.repo, self.base/'qualified', self.capture+timedelta(minutes=5))
        self.assertEqual(p['sample_classification'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
        self.update('vision.json', lambda d: d['cameras']['montrose_shoreline'].update(detectability='low'))
        self.commit()
        p = collect(self.repo, self.base/'dark', self.capture+timedelta(minutes=5))
        self.assertNotEqual(p['sample_classification'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
        self.qualify()
        p = collect(self.repo, self.base/'stale', self.capture+timedelta(hours=3))
        self.assertTrue(p['integrity_issues'])
        self.assertNotEqual(p['sample_classification'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
        self.update('vision.json', lambda d: d['cameras']['montrose_shoreline'].update(temporal_jubilee_signal='strong'))
        self.commit()
        p = collect(self.repo, self.base/'event', self.capture+timedelta(minutes=5))
        self.assertNotEqual(p['sample_classification'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')
        self.assertIn('vision.json', p['retained_sha256'])  # Events are collected too.

    def test_dirty_missing_and_output_guards(self):
        with self.assertRaises(ValueError):
            collect(self.repo, self.repo/'output')
        self.update('status.json', lambda d: d.update(capture_time_ct='2026-10-02T07:00:00'))
        with self.assertRaises(ValueError):
            collect(self.repo, self.base/'bad-time')
        self.update('status.json', lambda d: d.update(capture_time_ct=self.capture.isoformat()))
        with self.assertRaises(ValueError):
            collect(self.repo, self.base/'dirty')
        self.commit()
        self.git('rm', 'montrose_shoreline.jpg')
        self.git('commit', '-qm', 'missing media')
        p = collect(self.repo, self.base/'missing', self.capture+timedelta(minutes=5))
        self.assertIn('montrose_shoreline.jpg', p['missing_files'])
        self.assertIn('LATEST_IMAGE_INTEGRITY_FAILED', p['integrity_issues'])
        self.assertNotEqual(p['sample_classification'], 'CANDIDATE_VISIBLE_SCOPE_CONTROL')

    def test_october_two_labels_stay_bounded(self):
        audit = json.loads((ROOT/'model_data/j10_matched_control_sensitivity_20261002.json').read_text())
        self.assertEqual(len(audit['records']), 12)
        classes = []
        for row in audit['records']:
            record = json.loads((ROOT/row['path']).read_text())
            cell = next(c for c in record['cells'] if c['shoreline_cell'] == 'Montrose')
            classes.append(cell['control_eligibility'])
            self.assertEqual(record['clean_training_negative_count'], 0)
        self.assertEqual(classes.count('CANDIDATE_VISIBLE_SCOPE_CONTROL'), 6)
        self.assertEqual(classes.count('UNKNOWN_PRIMARY_CONTACT_VIEW_INADEQUATE'), 6)


if __name__ == '__main__':
    unittest.main()

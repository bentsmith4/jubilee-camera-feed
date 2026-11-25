"""Guard source chronology, episode deduplication and prior-history preservation."""
import hashlib
import json
from datetime import date
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'model_data'
NEW = {'1947-06-13-point-clear', '1947-06-14-point-clear', '1950-08-05-north-montrose'}

def load(name):
    return json.loads((ROOT / name).read_text())

class NewspaperAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.history = load('event_history.json')
        self.rows = {e['event_id']: e for e in self.history['events']}
        self.scan = load('loesch_newspaper_scan_evidence_20261003.json')

    def test_prior_sixteen_and_source_audit_unchanged(self):
        self.assertEqual(len(self.rows), 19)
        self.assertEqual(len(self.history['events']), 19)
        self.history['events'] = [e for e in self.history['events'] if e['event_id'] not in NEW]
        self.assertEqual(len(self.history['events']), 16)
        frozen_path = ROOT.parent / 'research' / 'matched_control_archive' / 'e634fdfd50a75dd358fc86e745a57fe18e856e9b749959bfd809b0b067fb697d' / 'packet' / 'model_data' / 'event_history.json'
        frozen = json.loads(frozen_path.read_text())
        target = '2024-08-05-mobile-bay-eastern-shore'
        current_unaffected = {e['event_id']: e for e in self.history['events'] if e['event_id'] != target}
        frozen_unaffected = {e['event_id']: e for e in frozen['events'] if e['event_id'] != target}
        # The separately admitted Daphne row is the only unaffected row not in
        # the older frozen packet.
        self.assertEqual(set(current_unaffected) - set(frozen_unaffected), {'1950-09-17-daphne'})
        current_unaffected.pop('1950-09-17-daphne')
        self.assertEqual(current_unaffected, frozen_unaffected)
        source = (ROOT / 'loesch_newspaper_scan_evidence_20261003.json').read_bytes()
        git_blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
        self.assertEqual(git_blob, '140552f7fd419dc59666c3fb567b883c6c572781')

    def test_calendar_and_provenance_not_publication_labels(self):
        for day, weekday in [('1947-06-13',4),('1947-06-14',5),('1947-06-16',0),('1950-08-05',5),('1950-08-06',6),('1950-08-07',0)]:
            self.assertEqual(date.fromisoformat(day).weekday(), weekday)
        for eid in NEW:
            e = self.rows[eid]; ev = e['evidence'][0]
            o = next(o for o in self.scan['observations'] if o['id']==ev['source_observation_id'])
            s = next(s for s in self.scan['sources'] if s['publication_date']==o['source'])
            self.assertEqual(e['event_date_ct'], o['event_date'])
            self.assertNotEqual(e['event_date_ct'], ev['source_publication_date'])
            self.assertEqual(ev['source_sha256'], s['sha256'])
            self.assertEqual(e['reported_species'], o['species'])
            self.assertTrue(e['research_only'])
            self.assertEqual(e['production_weight'], 0)
            self.assertFalse(e['calibration_eligible'])
            self.assertFalse(e['whole_day_negative_inference_allowed'])
            self.assertTrue(e['time_standard'].startswith('UNKNOWN'))
            self.assertFalse(e['location']['continuous_boundary_claimed'])

    def test_occurrences_are_not_independent_sources_or_location_counts(self):
        june = [self.rows[eid] for eid in sorted(NEW) if eid.startswith('1947')]
        self.assertEqual(june[0]['evidence'][0]['independence_group'], june[1]['evidence'][0]['independence_group'])
        self.assertEqual(june[0]['reported_species'], [])
        self.assertIn('inferred', june[0]['location']['precision'])
        august = [e for e in self.rows.values() if (e.get('event_date_ct') or '').startswith('1950-08')]
        self.assertEqual(len(august), 1)
        self.assertEqual(august[0]['continuation_dates_local'], ['1950-08-06'])
        self.assertNotIn('1950-08-07', august[0]['continuation_dates_local'])
        observations = {o['id'] for o in self.scan['observations']}
        for oid in ['1950-08-06-point-clear-report','1950-08-07-daphne-report']:
            self.assertIn(oid, observations)
            self.assertFalse(any(ev.get('source_observation_id')==oid for e in self.rows.values() for ev in e['evidence']))

if __name__ == '__main__':
    unittest.main()

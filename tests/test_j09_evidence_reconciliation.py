import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
import reconcile_j09_handoff as reconciliation

class NavigationReconciliationTests(unittest.TestCase):
    def test_all_four_actual_sentences_pass_simple_screen_but_fail_course_range(self):
        report = json.loads((ROOT / 'model_data/j09_pointclear_evidence_reconciliation_20260930.json').read_text())
        records = report['simple_only_RMC_records']
        self.assertEqual(len(records), 4)
        self.assertEqual([r['source_line'] for r in records], [19410, 81367, 132649, 133305])
        for record in records:
            self.assertEqual(reconciliation.screen(record['sentence']), (True, 'invalid_rmc_speed_or_course'))
            self.assertEqual(record['course_true_deg'], 360.0)
            # Changing only the course and recomputing checksum isolates the
            # rejected predicate, rather than relying on the error label.
            body = record['sentence'][1:].split('*')[0].replace(',360.0,', ',0.0,')
            checksum = 0
            for byte in body.encode('ascii'):
                checksum ^= byte
            self.assertEqual(reconciliation.screen(f'${body}*{checksum:02X}'), (True, None))

    def test_checksum_corruption_cannot_enter_either_selection(self):
        sentence = '$GPRMC,131022,A,3015.0150,N,08802.3674,W,4.7,360.0,211010,0.9,W,A*00'
        self.assertEqual(reconciliation.screen(sentence), (False, None))

    def test_preserved_reviewed_supporting_files_keep_hashes(self):
        manifest = json.loads((reconciliation.REVIEW / 'provenance.json').read_text())
        for name, expected in manifest['supporting_file_sha256'].items():
            self.assertEqual(reconciliation.digest((reconciliation.REVIEW / name).read_bytes()), expected, name)

if __name__ == '__main__':
    unittest.main()

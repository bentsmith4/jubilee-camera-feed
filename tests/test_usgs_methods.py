import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model_data'))
import ingest_river_forcing as river

NOW = datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc)

def document(code='00060', qualifiers=None, definitions=None, methods=None):
    return {'value': {'timeSeries': [{
        'name': 'USGS:02428400:' + code + ':00000',
        'sourceInfo': {'siteCode': [{'value': '02428400'}]},
        'variable': {'variableCode': [{'value': code}], 'unit': {'unitCode': 'ft3/s'}, 'noDataValue': -999999},
        'values': [{'method': methods or [{'methodID': 2974, 'methodDescription': ''}],
                    'qualifier': definitions or [],
                    'value': [{'dateTime': NOW.isoformat(), 'value': '100', 'qualifiers': qualifiers or ['P']}]}]
    }]}}

class USGSMethodTests(unittest.TestCase):
    def test_estimated_flow_eligible_only_with_documented_meaning(self):
        doc = document(qualifiers=['P', 'e'], definitions=[{'qualifierCode': 'e', 'qualifierDescription': 'Value has been estimated.'}])
        row = river.normalize(doc, NOW, 'test')[0]
        self.assertTrue(row['research_qc_eligible'])
        self.assertTrue(row['is_estimated'])
    def test_unexplained_flag_excluded(self):
        row = river.normalize(document(qualifiers=['P', 'e']), NOW, 'test')[0]
        self.assertFalse(row['research_qc_eligible'])
    def test_unknown_qualifier_excluded(self):
        row = river.normalize(document(qualifiers=['P', 'unknown']), NOW, 'test')[0]
        self.assertFalse(row['research_qc_eligible'])
    def test_identical_openings_on_different_gates_not_deduplicated(self):
        doc = document(code='45592', methods=[{'methodID': 1, 'methodDescription': 'GATE 1'}])
        second = copy.deepcopy(doc['value']['timeSeries'][0]['values'][0])
        second['method'] = [{'methodID': 2, 'methodDescription': 'GATE 2'}]
        doc['value']['timeSeries'][0]['values'].append(second)
        rows = river.normalize(doc, NOW, 'test')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['series_id'] for r in rows}), 2)
    def test_gate_label_preserved(self):
        doc = document(code='45592', methods=[{'methodID': 123, 'methodDescription': 'GATE 6'}])
        row = river.normalize(doc, NOW, 'test')[0]
        self.assertEqual(row['method_label'], 'GATE 6')
        self.assertEqual(row['method_id'], '123')

if __name__ == '__main__':
    unittest.main()

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



class FishRiverTests(unittest.TestCase):
    FIXTURE = Path(__file__).resolve().parent / 'fixtures/fish_river'

    def setUp(self):
        import json
        self.payload = (self.FIXTURE / 'usgs_02378500_20261018.json').read_bytes()
        self.doc = json.loads(self.payload)
        self.receipt = json.loads((self.FIXTURE / 'receipt.json').read_bytes())
        self.now = river.utc(self.receipt['retained_at_utc'])

    def rows(self):
        return river.normalize(self.doc, self.now, self.receipt['source_url'])

    def test_exact_public_fixture_identity_units_methods_qc_and_time(self):
        import hashlib
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), self.receipt['raw_sha256'])
        rows = self.rows()
        self.assertEqual(len(rows), 188)
        self.assertTrue(all(r['station_id'] == '02378500' and r['qualifiers'] == 'P'
                            and r['research_qc_eligible'] and r['production_weight'] == 0 for r in rows))
        self.assertEqual({(r['parameter_code'], r['unit'], r['method_id']) for r in rows},
                         {('00060', 'ft3/s', '2830'), ('00065', 'ft', '227878')})
        self.assertTrue(all(r['source_class'] == river.FISH_SOURCE_CLASS for r in rows))
        self.assertTrue(all('Provisional data subject to revision.' in r['qualifier_definitions'] for r in rows))
        summary = {r['parameter_code']: r for r in river.summarize(rows, self.now)}
        self.assertEqual(summary['00060']['latest_value'], 57.3)
        self.assertEqual(summary['00065']['latest_value'], 0.73)
        self.assertEqual(summary['00060']['latest_at_utc'], '2026-10-18T12:30:00+00:00')
        for entry in summary.values():
            self.assertEqual(entry['aggregation_policy'], 'DO_NOT_ADD_TO_UPSTREAM_OR_NESTED_GAUGES')
            self.assertNotIn('antecedent_windows', entry)
            self.assertTrue(entry['fresh'])
        self.assertEqual(summary['00065']['vertical_reference'],
                         'native_local_gage_datum_not_tidal_or_NAVD88_elevation')

    def test_identity_and_geometry_mismatches_are_fatal(self):
        for kind in ('agency', 'network', 'station', 'latitude', 'longitude', 'crs', 'series', 'multiple_ids'):
            with self.subTest(kind=kind):
                self.setUp()
                ts = self.doc['value']['timeSeries'][0]
                ident = ts['sourceInfo']['siteCode'][0]
                location = ts['sourceInfo']['geoLocation']['geogLocation']
                if kind == 'agency': ident['agencyCode'] = 'OTHER'
                elif kind == 'network': ident['network'] = 'OTHER'
                elif kind == 'station': ident['value'] = '99999999'
                elif kind == 'latitude': location['latitude'] += 1
                elif kind == 'longitude': location['longitude'] += 1
                elif kind == 'crs': location['srs'] = 'UNKNOWN'
                elif kind == 'multiple_ids': ts['sourceInfo']['siteCode'].append(copy.deepcopy(ident))
                else: ts['name'] = 'USGS:02428400:00060:00000'
                with self.assertRaises(ValueError): self.rows()

    def test_units_unrecognized_parameters_and_unresolved_methods_are_not_admitted(self):
        for kind in ('units', 'parameter', 'methods', 'empty_method', 'bad_method'):
            with self.subTest(kind=kind):
                self.setUp()
                ts = self.doc['value']['timeSeries'][0]
                if kind == 'units': ts['variable']['unit']['unitCode'] = 'm3/s'
                elif kind == 'parameter':
                    ts['variable']['variableCode'][0]['value'] = '00045'
                    ts['name'] = 'USGS:02378500:00045:00000'
                elif kind == 'methods': ts['values'][0]['method'] = []
                else: ts['values'][0]['method'][0]['methodID'] = '' if kind == 'empty_method' else 'UNKNOWN'
                rows = self.rows()
                self.assertFalse(any(r['research_qc_eligible'] for r in rows[:94]))
                self.assertTrue(all(r['research_qc_eligible'] for r in rows[94:]))

    def test_future_negative_discharge_and_unknown_qc_are_not_admitted(self):
        from datetime import timedelta
        for kind in ('future', 'negative', 'unknown_qc', 'undocumented_estimate'):
            with self.subTest(kind=kind):
                self.setUp()
                values = self.doc['value']['timeSeries'][0]['values'][0]['value']
                for v in values:
                    if kind == 'future': v['dateTime'] = (self.now + timedelta(minutes=1)).isoformat()
                    elif kind == 'negative': v['value'] = '-1'
                    else: v['qualifiers'] = ['P', 'e' if kind == 'undocumented_estimate' else 'UNKNOWN']
                self.assertFalse(any(r['research_qc_eligible'] for r in self.rows() if r['parameter_code'] == '00060'))

    def test_bad_values_and_missing_clock_are_not_zero(self):
        for bad in ('NaN', 'Infinity', '-999999', None):
            with self.subTest(bad=bad):
                self.setUp()
                for ts in self.doc['value']['timeSeries']:
                    for v in ts['values'][0]['value']: v['value'] = bad
                self.assertEqual(self.rows(), [])
        self.setUp()
        for ts in self.doc['value']['timeSeries']:
            for v in ts['values'][0]['value']: v['dateTime'] = '2026-10-18T12:30:00'
        self.assertEqual(self.rows(), [])

    def test_separate_methods_preserve_equal_values_and_no_aggregate(self):
        ts = self.doc['value']['timeSeries'][0]
        second = copy.deepcopy(ts['values'][0])
        second['method'][0]['methodID'] = 999
        ts['values'].append(second)
        summary = river.summarize(self.rows(), self.now)
        self.assertEqual(len(summary), 3)
        self.assertEqual({s['method_id'] for s in summary}, {'2830', '999', '227878'})
        self.assertTrue(all('antecedent_windows' not in s for s in summary))

    def test_stale_future_and_exact_freshness_boundary(self):
        from datetime import timedelta
        rows = self.rows()
        observed = river.utc('2026-10-18T12:30:00+00:00')
        for delta, expected in ((-1, False), (180, True), (180.001, False)):
            with self.subTest(delta=delta):
                self.assertTrue(all(s['fresh'] is expected for s in river.summarize(rows, observed + timedelta(minutes=delta))))

    def test_legacy_three_station_rows_unchanged_after_expansion(self):
        old = document()
        for station in river.UPSTREAM_SITES[1:]:
            ts = copy.deepcopy(old['value']['timeSeries'][0])
            ts['sourceInfo']['siteCode'][0]['value'] = station
            ts['name'] = 'USGS:' + station + ':00060:00000'
            old['value']['timeSeries'].append(ts)
        before = river.normalize(old, NOW, 'legacy-three-station-url')
        mixed = copy.deepcopy(old)
        mixed['value']['timeSeries'].extend(self.doc['value']['timeSeries'])
        after = river.normalize(mixed, NOW, 'legacy-three-station-url')
        self.assertEqual(before, [r for r in after if r['station_id'] in river.UPSTREAM_SITES])
        self.assertEqual({r['station_id'] for r in before}, set(river.UPSTREAM_SITES))
        self.assertTrue(all(r['source_class'] == 'agency_reported_upstream_forcing_not_bay_inflow' for r in before))

    def test_collector_reuses_request_hash_archive_and_partial_coverage(self):
        import contextlib
        import gzip
        import hashlib
        import io
        import json
        import tempfile
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlparse
        for payload, expected_missing in ((self.payload, list(river.UPSTREAM_SITES)),
                                          (b'{"value":{"timeSeries":[]}}', sorted(river.SITES))):
            with self.subTest(missing=expected_missing), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                with patch.object(river, 'HERE', directory), patch.object(river, 'fetch', return_value=payload) as fetch, \
                        patch.object(sys, 'argv', ['ingest_river_forcing.py', '--days', '16']), contextlib.redirect_stdout(io.StringIO()):
                    river.main()
                m = json.loads((directory / 'river_forcing_manifest.json').read_text())
                self.assertEqual(m['status'], 'partial')
                self.assertEqual(m['missing_sites'], sorted(expected_missing))
                query = parse_qs(urlparse(fetch.call_args.args[0]).query)
                self.assertEqual(query['sites'], [','.join(river.SITES)])
                self.assertEqual(query['period'], ['P16D'])
                self.assertEqual(m['raw_sha256'], hashlib.sha256(payload).hexdigest())
                self.assertEqual(gzip.decompress((directory / m['raw_path']).read_bytes()), payload)
                self.assertEqual(m['local_watershed_missing_parameter_codes'], [] if payload == self.payload else ['00060', '00065'])
                self.assertEqual(m['series'], [])
                self.assertEqual(len(m['local_watershed_series']), 2 if payload == self.payload else 0)
                self.assertTrue(all(r['station_id'] == river.FISH_RIVER for r in m['local_watershed_series']))
                self.assertEqual(m['production_action'], 'NO_CHANGE')
                self.assertFalse(m['action_required'])


    def test_registry_reconciler_preserves_separate_source_without_actual_write(self):
        import contextlib
        import io
        import json
        import tempfile
        from unittest.mock import Mock, patch
        import reconcile_source_registry as registry
        fish_entry = {'source_id': 'usgs_02378500_fish_river', 'source_class': 'local_watershed_forcing_proxy',
                      'status': 'registered_current_availability_requires_api_check', 'production_weight': 0}
        upstream_ids = ('usgs_02428400_claiborne', 'usgs_02469761_02469762_coffeeville')
        original = {'sources': [fish_entry] + [{'source_id': sid} for sid in upstream_ids] +
                   [{'source_id': 'noaa_ngofs2_mobile_bay'}]}
        manifest = {'status': 'complete', 'normalized_rows': 189, 'retrieved_at_utc': self.now.isoformat(),
                    'series': river.summarize(river.normalize(document(), NOW, 'legacy'), self.now),
                    'local_watershed_series': river.summarize(self.rows(), self.now)}
        target = Mock()
        target.read_text.return_value = json.dumps(original)
        with tempfile.TemporaryDirectory() as tmp, patch.object(registry, 'HERE', Path(tmp)), \
                patch.object(registry, 'REGISTRY', target), \
                patch.object(registry, 'load', side_effect=lambda name: manifest if name == 'river_forcing_manifest.json' else None), \
                contextlib.redirect_stdout(io.StringIO()):
            registry.main()
        actual = {r['source_id']: r for r in json.loads(target.write_text.call_args.args[0])['sources']}
        self.assertEqual(actual[fish_entry['source_id']], fish_entry)
        for sid in upstream_ids:
            self.assertNotIn(river.FISH_RIVER, actual[sid]['station_health'])
        target.write_text.assert_called_once()

    def test_missing_single_parameter_and_outage_are_explicit(self):
        import contextlib
        import io
        import json
        import tempfile
        from unittest.mock import patch
        self.doc['value']['timeSeries'] = self.doc['value']['timeSeries'][:1]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch.object(river, 'HERE', directory), patch.object(river, 'fetch', return_value=json.dumps(self.doc).encode()), \
                    patch.object(sys, 'argv', ['ingest_river_forcing.py']), contextlib.redirect_stdout(io.StringIO()):
                river.main()
            m = json.loads((directory / 'river_forcing_manifest.json').read_text())
            self.assertEqual(m['local_watershed_missing_parameter_codes'], ['00065'])
            self.assertEqual(len(m['local_watershed_series']), 1)
        details = river.failure_details(TimeoutError(), {}, self.now)
        self.assertEqual(details['local_watershed_series'], [])
        self.assertEqual(details['local_watershed_missing_parameter_codes'], ['00060', '00065'])



if __name__ == '__main__':
    unittest.main()

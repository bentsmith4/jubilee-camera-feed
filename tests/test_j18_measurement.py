import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'model_data/j18_measurement'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE/filename)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m = module('measurement', 'measurement.py')
v = module('compression', 'validate_compression.py')


class MeasurementTests(unittest.TestCase):
    def row(self, **changes):
        r = dict(recorded_at_ct='2026-10-03T10:30:00+00:00', stage='camera:montrose_shoreline',
                 model='gpt-5.6-luna', status='completed', output_text_present=True,
                 input_tokens=100, cached_input_tokens=40, output_tokens=20,
                 reasoning_output_tokens=5, total_tokens=120, response_id='PRIVATE', prompt='PRIVATE')
        r.update(changes)
        return r

    def export(self, rows, manifests=()):
        return m.export(b'\n'.join(json.dumps(r).encode() for r in rows), b'x'*32, manifests)

    def test_real_legacy_shape_stays_unknown_and_strips_private_values(self):
        data = self.export([self.row()])
        self.assertNotIn('PRIVATE', json.dumps(data))
        r = data['rows'][0]
        for f in ('capture_key', 'camera_integrity', 'runtime_version', 'service_tier', 'context_class'):
            self.assertEqual(r[f], 'UNKNOWN')
        self.assertIsNone(r['tokens']['cache_write_tokens'])
        self.assertEqual(r['time_bin_ct'], '04-08')
        self.assertEqual(m.diagnose(data)['cohorts'][0]['cache_read_fraction'], .4)

    def test_exact_capture_binding_and_no_time_guess(self):
        receipt = json.dumps(dict(capture_id='PRIVATE_CAPTURE', capture_time_ct='2026-10-03T05:30:00-05:00',
            runtime_version='version-1', cameras={'montrose_shoreline':{'capture_ok':True, 'integrity_issues':[]}})).encode()
        unbound = self.export([self.row()], [receipt])['rows'][0]
        bound = self.export([self.row(capture_id='PRIVATE_CAPTURE')], [receipt])['rows'][0]
        self.assertEqual(unbound['capture_key'], 'UNKNOWN')
        self.assertNotEqual(bound['capture_key'], 'UNKNOWN')
        self.assertTrue(bound['camera_integrity'])
        self.assertEqual(bound['runtime_version'], 'version-1')
        self.assertNotIn('PRIVATE_CAPTURE', json.dumps(bound))

    def test_cross_camera_integrity_requires_all_six_and_low_light_not_failure(self):
        receipt = dict(capture_id='c', cameras={c:dict(capture_ok=True, integrity_issues=[], detectability='low') for c in m.CAMERAS})
        data = self.export([self.row(capture_id='c', stage='cross_camera')], [json.dumps(receipt).encode()])
        self.assertIs(data['rows'][0]['camera_integrity'], True)
        del receipt['cameras'][m.CAMERAS[0]]
        self.assertEqual(self.export([self.row(capture_id='c', stage='cross_camera')], [json.dumps(receipt).encode()])['rows'][0]['camera_integrity'], 'UNKNOWN')

    def test_duplicate_malformed_and_invalid_subset_block_complete_export(self):
        for rows in ([self.row(), self.row()], [self.row(cached_input_tokens=101)], [self.row(recorded_at_ct='2026-10-03T05:30:00')]):
            self.assertGreater(self.export(rows)['invalid_records'], 0)
        self.assertEqual(self.export([self.row(status='request_failed', input_tokens=None, output_tokens=None, total_tokens=None)])['rows'][0]['status'], 'request_failed')

    def test_write_counts_are_not_inferred_and_bad_partition_rejected(self):
        r = self.export([self.row(cache_write_tokens=10)])['rows'][0]
        self.assertEqual(r['tokens']['cache_write_tokens'], 10)
        self.assertEqual(r['cache_write_semantics'], 'UNKNOWN')
        self.assertEqual(self.export([self.row(cache_write_tokens=61, cache_write_semantics='partition_of_input')])['invalid_records'], 1)


class CompressionTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((HERE/'protocol.json').read_text())
        self.config = json.loads((ROOT/'model_data/j18_cost_accounting/pricing_assumptions.json').read_text())

    def corpus(self, cases):
        return dict(cases=cases, development_group_ids=[],
                    protocol_sha256=v.sha((HERE/'protocol.json').read_bytes()),
                    candidate_sha256=v.sha((HERE/'candidate_instruction.txt').read_bytes()))

    def case(self, label='EVENT'):
        attempt = dict(rate_key='gpt-5.6-luna', cache_write_semantics='partition_of_input',
            tokens=dict(input_tokens=100, cached_input_tokens=40, cache_write_tokens=10,
                        output_tokens=20, reasoning_output_tokens=5, total_tokens=120))
        arm = dict(input_sha256='a'*64, downstream_sha256='b'*64,
            model='gpt-5.6-luna', service_tier='standard', context_class='short',
            camera_coverage=6, synthesis_policy='unchanged', runtime_version='v1',
            event_alert=label=='EVENT', unknown_preserved=True, safety_correct=True,
            finish_status='completed', schema_valid=True,
            attempts=[dict(copy.deepcopy(attempt), stage=s) for s in v.ACCOUNTING.STAGES])
        return dict(case_id='1', group_id='morning-1', split='held_out', label=label,
            label_basis={'EVENT':'independent_verified_event','NON_EVENT':'independent_scoped_control',
                         'UNKNOWN':'independent_unknown_review','SAFETY':'independent_safety_review'}[label],
            geometric_scope='visible footprint only', label_provenance='independent fixture reviewer',
            frozen_before_replay=True, input_sha256='a'*64, rubric_sha256='c'*64,
            downstream_sha256='b'*64, baseline=copy.deepcopy(arm), candidate=copy.deepcopy(arm))

    def test_missing_corpus_blocks_and_never_recommends_production(self):
        result = v.evaluate(self.corpus([]), self.protocol, self.config)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['conditional_savings'], 'UNKNOWN')
        self.assertEqual(result['recommendation'], 'NO_PRODUCTION_CHANGE')

    def test_pinned_real_low_light_fixture_roundtrips_without_field_loss(self):
        source = json.loads((ROOT/'tests/fixtures/vision_quiet_low_detectability_20260927.json').read_text())
        encoded = v.compact(source)
        self.assertEqual(json.loads(encoded), source)
        self.assertIsNone(json.loads(encoded)['cameras']['pcl_e2_back_deck']['human_sensor_score'])
        self.assertEqual(json.loads(encoded)['cameras']['pcl_e2_back_deck']['detectability'], 'low')

    def test_event_false_alert_unknown_and_safety_regressions_block(self):
        for label, field, value, blocker in (
            ('EVENT','event_alert',False,'Lost baseline event detection'),
            ('NON_EVENT','event_alert',True,'Added scoped false alert'),
            ('UNKNOWN','unknown_preserved',False,'UNKNOWN handling failure'),
            ('SAFETY','safety_correct',False,'Safety failure')):
            c = self.case(label)
            c['candidate'][field] = value
            result = v.evaluate(self.corpus([c]), self.protocol, self.config)
            self.assertIn(blocker, result['blockers'])

    def test_leakage_social_silence_and_mismatched_media_rejected(self):
        c = self.case()
        corpus = self.corpus([c])
        corpus['development_group_ids'] = ['morning-1']
        with self.assertRaises(ValueError): v.evaluate(corpus, self.protocol, self.config)
        c['label_basis'] = 'social_silence'
        with self.assertRaises(ValueError): v.evaluate(self.corpus([c]), self.protocol, self.config)
        c = self.case()
        c['candidate']['input_sha256'] = 'd'*64
        with self.assertRaises(ValueError): v.evaluate(self.corpus([c]), self.protocol, self.config)

    def test_missing_usage_blocks_savings_and_all_attempts_are_charged(self):
        c = self.case()
        one = v.cost(c['baseline'], self.config['rates'])
        c['baseline']['attempts'] *= 2
        two = v.cost(c['baseline'], self.config['rates'])
        self.assertAlmostEqual(two['cost_lower_usd'], 2*one['cost_lower_usd'])
        c['candidate']['attempts'][0]['tokens']['input_tokens'] = None
        self.assertEqual(v.evaluate(self.corpus([c]), self.protocol, self.config)['conditional_savings'], 'UNKNOWN')


if __name__ == '__main__': unittest.main()

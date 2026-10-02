"""Accounting identities, adversarial missingness, and pinned audit reconciliation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'model_data/j18_cost_accounting'
SPEC = importlib.util.spec_from_file_location('j18_accounting', HERE/'accounting.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.usage = json.loads((HERE/'usage_20261002.json').read_text())
        self.config = json.loads((HERE/'pricing_assumptions.json').read_text())

    def selected(self):
        return next(g for g in self.usage['groups'] if g['date_ct'] == '2026-09-19')

    def test_disjoint_billing_categories_and_reasoning_subset(self):
        t = dict(input_tokens=100, cached_input_tokens=40, output_tokens=20,
                 reasoning_output_tokens=10, total_tokens=120)
        r = dict(input_per_million=2, cached_input_per_million=.2,
                 cache_write_per_million=2.5, output_per_million=10)
        # 50 ordinary + 40 reads + 10 writes + 20 output, reasoning already included.
        parts = a.cost_parts(t, r, 10)
        self.assertAlmostEqual(sum(parts.values()), .000333)
        self.assertEqual(set(parts), {'ordinary_input', 'cached_input', 'cache_write', 'output_including_reasoning'})
        with self.assertRaises(ValueError):
            a.cost_parts(t, r, 61)

    def test_known_writes_collapse_bounds_and_missing_writes_do_not_default_zero(self):
        g = copy.deepcopy(self.selected())
        _, _, low, high, unknown = a.price_group(g, self.config['rates'])
        self.assertTrue(unknown)
        self.assertGreater(high, low)
        g['tokens']['cache_write_tokens'] = {'known_sum': 100, 'missing_records': 0}
        _, _, low, high, unknown = a.price_group(g, self.config['rates'])
        self.assertFalse(unknown)
        self.assertEqual(low, high)

    def test_reconciles_october_audit_and_preserves_incomplete_attempt_costs(self):
        result = a.build(self.usage, self.config)
        post = result['postdeployment']
        self.assertEqual(post['completed_requests'], 2688)
        self.assertEqual(post['reference_requests'], 418)
        self.assertEqual(post['stages']['cross_camera']['completed_requests'], 286)
        self.assertEqual(post['logged_requests'], 2690)
        self.assertEqual(post['other_status_requests'], 2)
        self.assertEqual(post['failed_requests'], 0)
        self.assertIsNone(post['valid_six_camera_cycles'])
        self.assertEqual(result['production_changes'], [])
        audit = json.loads((ROOT/'model_data/j18_efficiency_postdeployment_20261002.json').read_text())
        for label in ('baseline', 'postdeployment'):
            p = result[label]
            camera_tokens = sum(p['stages'][s]['tokens']['total_tokens']/p['stages'][s]['completed_requests'] for s in a.STAGES[:-1])
            cross_tokens = p['stages']['cross_camera']['tokens']['total_tokens']/p['reference_requests']
            self.assertAlmostEqual(camera_tokens, audit['metrics']['six_camera_tokens_per_reference_request'][label])
            self.assertAlmostEqual(camera_tokens+cross_tokens, audit['metrics']['request_normalized_total_tokens'][label])

    def test_committed_report_reproduces_and_source_matches_audit_blob(self):
        stored = json.loads((HERE/'report_20261002.json').read_text())
        source = stored.pop('source')
        self.assertEqual(stored, a.build(self.usage, self.config))
        raw = (HERE/'usage_20261002.json').read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(blob, 'eeef7e54ad2d40d96cf1f5430258f919c256e713')
        self.assertEqual(blob, source['usage_git_blob_sha'])
        self.assertEqual(hashlib.sha256((HERE/'pricing_assumptions.json').read_bytes()).hexdigest(), source['pricing_sha256'])

    def test_failed_attempt_costs_are_charged_without_completed_work_credit(self):
        baseline = a.build(self.usage, self.config)['postdeployment']
        g = self.selected()
        g['completed_requests'] -= 1
        g['failed_requests'] += 1
        changed = a.build(self.usage, self.config)['postdeployment']
        self.assertEqual(changed['completed_requests'], baseline['completed_requests']-1)
        self.assertEqual(changed['failed_requests'], 1)
        self.assertEqual(changed['mean_logged_cost_per_calendar_complete_day'], baseline['mean_logged_cost_per_calendar_complete_day'])
        self.assertGreater(changed['six_camera_standardized_cost_per_reference_request']['cost_lower_usd'], baseline['six_camera_standardized_cost_per_reference_request']['cost_lower_usd'])

    def test_same_work_camera_normalization_does_not_reward_missing_camera_calls(self):
        original = a.build(self.usage, self.config)['postdeployment']['six_camera_standardized_cost_per_reference_request']
        for g in self.usage['groups']:
            if g['date_ct'] >= '2026-09-19' and g['stage'] == 'camera:pcl_e3_bay_mouth':
                for k in ('completed_requests', 'logged_requests'):
                    g[k] *= 2
                for token in g['tokens'].values():
                    token['known_sum'] *= 2
        changed = a.build(self.usage, self.config)['postdeployment']['six_camera_standardized_cost_per_reference_request']
        self.assertEqual(original, changed)

    def test_missing_day_and_missing_token_fail_closed(self):
        self.selected()['tokens']['input_tokens']['missing_records'] = 1
        with self.assertRaises(ValueError):
            a.build(self.usage, self.config)
        self.setUp()
        self.usage['groups'] = [g for g in self.usage['groups'] if g['date_ct'] != '2026-09-19']
        with self.assertRaises(ValueError):
            a.build(self.usage, self.config)

    def test_partial_day_duplicate_unknown_model_and_invalid_tokens_rejected(self):
        self.config['postdeployment']['end'] = '2026-10-02'
        with self.assertRaises(ValueError): a.build(self.usage, self.config)
        self.setUp()
        self.usage['groups'].append(copy.deepcopy(self.selected()))
        with self.assertRaises(ValueError): a.build(self.usage, self.config)
        self.setUp()
        self.selected()['model'] = 'unrecognized_or_unavailable'
        with self.assertRaises(KeyError): a.build(self.usage, self.config)
        self.setUp()
        self.selected()['tokens']['input_tokens']['known_sum'] = -1
        with self.assertRaises(ValueError): a.build(self.usage, self.config)

    def test_configured_rates_scale_costs_without_changing_work(self):
        result = a.build(self.usage, self.config)
        for rate in self.config['rates'].values():
            for k in list(rate):
                if k.endswith('_per_million'): rate[k] *= 2
        changed = a.build(self.usage, self.config)
        before = result['postdeployment']['representative_complete_day']
        after = changed['postdeployment']['representative_complete_day']
        for k in before: self.assertAlmostEqual(after[k], 2*before[k])
        del self.config['rates']['gpt-5.6-luna']['source_url']
        with self.assertRaises(ValueError): a.build(self.usage, self.config)


if __name__ == '__main__': unittest.main()

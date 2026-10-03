"""Offline paired replay evaluator; no API calls or production modifications."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import math

HERE = Path(__file__).resolve().parent
UNKNOWN = 'UNKNOWN'
SPEC = importlib.util.spec_from_file_location('j18_cost', HERE.parent / 'j18_cost_accounting/accounting.py')
ACCOUNTING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACCOUNTING)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def compact(output):
    """Lossless candidate: compact JSON; no fields, enums or text removed."""
    encoded = json.dumps(output, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if json.loads(encoded) != output:
        raise ValueError('Lossy output')
    return encoded


def wilson(successes, total):
    if total == 0:
        return UNKNOWN
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total))/denominator
    width = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denominator
    return [max(0., center-width), min(1., center+width)]


def metric(cases, arm, label, field, expected):
    selected = [c for c in cases if c['label'] == label]
    n = len(selected)
    hits = sum(c[arm][field] == expected for c in selected)
    return dict(n=n, successes=hits, fraction=hits/n if n else UNKNOWN,
                wilson_95=wilson(hits, n))


def cost(arm, rates):
    low, high = 0., 0.
    # Include every charged attempt, not just successful paired completions.
    if not arm['attempts']:
        raise ValueError('Attempt usage required')
    for r in arm['attempts']:
        tokens = r['tokens']
        if any(type(tokens.get(f)) is not int for f in ACCOUNTING.FIELDS):
            return UNKNOWN
        group = {'model': r['rate_key'], 'tokens': {f: {'known_sum': tokens[f], 'missing_records': 0} for f in ACCOUNTING.FIELDS}}
        if tokens.get('cache_write_tokens') is not None and r.get('cache_write_semantics') == 'partition_of_input':
            group['tokens']['cache_write_tokens'] = {'known_sum': tokens['cache_write_tokens'], 'missing_records': 0}
        _, _, lo, hi, _ = ACCOUNTING.price_group(group, rates)
        low += lo
        high += hi
    return {'cost_lower_usd': low, 'cost_upper_usd': high}


def evaluate(corpus, protocol, config):
    if protocol != json.loads((HERE/'protocol.json').read_text()):
        raise ValueError('Protocol must match preregistered bytes')
    ACCOUNTING.validate_config(config)
    cases = corpus['cases']
    result = dict(schema_version=1, status='BLOCKED', recommendation='NO_PRODUCTION_CHANGE',
                  cases=len(cases), blockers=[], metrics={}, conditional_savings=UNKNOWN,
                  production_changes=[])
    if corpus.get('protocol_sha256') != sha((HERE/'protocol.json').read_bytes()):
        result['blockers'].append('Protocol bytes not bound to frozen corpus')
    if corpus.get('candidate_sha256') != sha((HERE/'candidate_instruction.txt').read_bytes()):
        result['blockers'].append('Candidate bytes not bound to frozen corpus')
    if not cases:
        result['blockers'].append('No independent held-out labeled paired replays')
        return result
    ids, groups = set(), set()
    for c in cases:
        if c['case_id'] in ids:
            raise ValueError('Duplicate case')
        ids.add(c['case_id'])
        if c['split'] != 'held_out' or c['group_id'] in corpus.get('development_group_ids', []):
            raise ValueError('Development/held-out leakage')
        groups.add(c['group_id'])
        if c['label'] not in ('EVENT', 'NON_EVENT', 'UNKNOWN', 'SAFETY'):
            raise ValueError('Invalid label')
        if c['label_basis'] not in ('independent_verified_event', 'independent_scoped_control',
                                    'independent_unknown_review', 'independent_safety_review'):
            raise ValueError('Labels must be independently adjudicated; no social-silence negatives')
        expected_basis = {'EVENT':'independent_verified_event', 'NON_EVENT':'independent_scoped_control',
                          'UNKNOWN':'independent_unknown_review', 'SAFETY':'independent_safety_review'}
        if c['label_basis'] != expected_basis[c['label']]:
            raise ValueError('Label/basis mismatch')
        if not c.get('geometric_scope') or not c.get('label_provenance') or not c.get('frozen_before_replay'):
            raise ValueError('Scoped preregistered labels required')
        for field in ('input_sha256', 'rubric_sha256', 'downstream_sha256'):
            if not isinstance(c.get(field), str) or len(c[field]) != 64:
                raise ValueError('Replay inputs and unchanged decision adapter must be pinned')
        b, p = c['baseline'], c['candidate']
        for arm in (b, p):
            if arm['input_sha256'] != c['input_sha256'] or arm['downstream_sha256'] != c['downstream_sha256']:
                raise ValueError('Unmatched paired inputs/decision path')
            for f in ('event_alert', 'unknown_preserved', 'safety_correct'):
                if type(arm[f]) is not bool:
                    raise ValueError('Missing decision outcome')
            if arm.get('finish_status') != 'completed' or not arm.get('schema_valid'):
                result['blockers'].append('Incomplete or invalid structured output')
            stages = {r.get('stage') for r in arm['attempts']}
            if not set(ACCOUNTING.STAGES).issubset(stages):
                result['blockers'].append('Usage does not cover six cameras and synthesis')
        for f in ('model', 'service_tier', 'context_class', 'camera_coverage', 'synthesis_policy', 'runtime_version'):
            if b.get(f) in (None, UNKNOWN) or b.get(f) != p.get(f):
                result['blockers'].append('Unmatched or UNKNOWN replay condition: ' + f)
        if b.get('camera_coverage') != 6:
            result['blockers'].append('Replay must preserve all six cameras')
        if c['label'] == 'EVENT' and b['event_alert'] and not p['event_alert']:
            result['blockers'].append('Lost baseline event detection')
        if c['label'] == 'EVENT' and not p['event_alert']:
            result['blockers'].append('Missed independently labeled event')
        if c['label'] == 'NON_EVENT' and p['event_alert'] and not b['event_alert']:
            result['blockers'].append('Added scoped false alert')
        if c['label'] == 'UNKNOWN' and not p['unknown_preserved']:
            result['blockers'].append('UNKNOWN handling failure')
        if c['label'] == 'SAFETY' and not p['safety_correct']:
            result['blockers'].append('Safety failure')
    for name, label, field, expected in (
            ('event_sensitivity', 'EVENT', 'event_alert', True),
            ('scoped_false_alert_rate', 'NON_EVENT', 'event_alert', True),
            ('unknown_preservation', 'UNKNOWN', 'unknown_preserved', True),
            ('safety_correctness', 'SAFETY', 'safety_correct', True)):
        b, p = metric(cases, 'baseline', label, field, expected), metric(cases, 'candidate', label, field, expected)
        result['metrics'][name] = dict(baseline=b, candidate=p,
            change=p['fraction']-b['fraction'] if b['n'] else UNKNOWN)
        independent_groups = len({c['group_id'] for c in cases if c['label'] == label})
        result['metrics'][name]['independent_groups'] = independent_groups
        if independent_groups < protocol['minimum_independent_groups_per_label']:
            result['blockers'].append('Insufficient independent held-out groups: ' + label)
    costs = {arm: [cost(c[arm], config['rates']) for c in cases] for arm in ('baseline', 'candidate')}
    if any(x == UNKNOWN for values in costs.values() for x in values):
        result['blockers'].append('Missing charged-attempt usage')
    else:
        totals = {arm: {f: sum(x[f] for x in values) for f in ('cost_lower_usd', 'cost_upper_usd')} for arm, values in costs.items()}
        result['conditional_savings'] = dict(totals=totals,
            percent=ACCOUNTING.savings_range(totals['baseline'], totals['candidate']),
            basis=config['billing_status'])
        if totals['baseline']['cost_lower_usd'] <= totals['candidate']['cost_upper_usd']:
            result['blockers'].append('Positive savings not established across unknown-write bounds')
    result['blockers'] = sorted(set(result['blockers']))
    if not result['blockers']:
        result['status'] = 'ELIGIBLE_FOR_REVIEW_ONLY'
    result['limits'] = ['Wilson intervals are descriptive per case; repeated frames are not independent events.',
                       'Passing this screening gate does not prove statistical equivalence or authorize deployment.',
                       'List-price savings are conditional; account spend remains UNKNOWN without billing reconciliation.']
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus', type=Path, default=HERE/'held_out_cases.json')
    p.add_argument('--pricing', type=Path, default=HERE.parent/'j18_cost_accounting/pricing_assumptions.json')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = evaluate(json.loads(a.corpus.read_text()), json.loads((HERE/'protocol.json').read_text()), json.loads(a.pricing.read_text()))
    a.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

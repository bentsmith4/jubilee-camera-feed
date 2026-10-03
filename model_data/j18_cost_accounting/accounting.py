"""Offline research accounting. No runtime imports, API calls, or production writes."""
import argparse
import copy
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = (
    'montrose_pier_boat', 'montrose_pier_bird', 'montrose_shoreline',
    'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth',
)
STAGES = tuple('camera:' + c for c in CAMERAS) + ('cross_camera',)
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens',
          'reasoning_output_tokens', 'total_tokens')


def nonnegative(value, name, integer=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid ' + name)
    if integer and type(value) is not int:
        raise ValueError('Noninteger ' + name)
    return value


def validate_config(config):
    if config['currency'] != 'USD' or not config['rates']:
        raise ValueError('Explicit USD rates required')
    for model, rate in config['rates'].items():
        for field in ('input', 'cached_input', 'cache_write', 'output'):
            nonnegative(rate[field + '_per_million'], model + ':' + field)
        if not all(rate.get(k) for k in ('source_url', 'accounting_source_url', 'retrieved_on', 'basis')):
            raise ValueError('Rate provenance required')
        date.fromisoformat(rate['retrieved_on'])
    if config['reference_stage'] not in STAGES[:-1]:
        raise ValueError('Reference must be an explicit camera')
    for k in ('representative_dawn_reference_requests', 'representative_complete_day_reference_requests'):
        if not nonnegative(config[k], k, True):
            raise ValueError('Scenario work must be positive')
    fraction = nonnegative(config['candidate_camera_output_reduction_fraction'], 'candidate fraction')
    if fraction > 1:
        raise ValueError('Candidate fraction exceeds one')


def cost_parts(tokens, rate, writes):
    """Disjoint billed categories: ordinary input, cache read/write, all output."""
    ordinary = tokens['input_tokens'] - tokens['cached_input_tokens'] - writes
    if ordinary < 0 or writes < 0:
        raise ValueError('Cache subsets exceed input')
    return {
        'ordinary_input': ordinary * rate['input_per_million'] / 1e6,
        'cached_input': tokens['cached_input_tokens'] * rate['cached_input_per_million'] / 1e6,
        'cache_write': writes * rate['cache_write_per_million'] / 1e6,
        'output_including_reasoning': tokens['output_tokens'] * rate['output_per_million'] / 1e6,
    }


def price_group(group, rates):
    rate = rates[group['model']]  # No alias fallback or guessed account rate.
    tokens = {}
    for key in FIELDS:
        item = group['tokens'][key]
        if item['missing_records'] != 0:
            raise ValueError('Missing usage cannot be priced as zero')
        tokens[key] = nonnegative(item['known_sum'], key, True)
    if tokens['total_tokens'] != tokens['input_tokens'] + tokens['output_tokens']:
        raise ValueError('Inconsistent total tokens')
    if tokens['reasoning_output_tokens'] > tokens['output_tokens']:
        raise ValueError('Reasoning exceeds output')
    cap = tokens['input_tokens'] - tokens['cached_input_tokens']
    if cap < 0:
        raise ValueError('Cached input exceeds input')
    write_item = group['tokens'].get('cache_write_tokens')
    if write_item is not None and write_item['missing_records'] == 0:
        writes = nonnegative(write_item['known_sum'], 'cache writes', True)
        parts = cost_parts(tokens, rate, writes)
        return tokens, parts, sum(parts.values()), sum(parts.values()), False
    # Historical cache writes are unreported: all non-read input is the cap.
    parts = cost_parts(tokens, rate, 0)
    endpoints = [sum(parts.values()), sum(cost_parts(tokens, rate, cap).values())]
    return tokens, parts, min(endpoints), max(endpoints), True


def period(summary, config, window):
    first, last = date.fromisoformat(window['start']), date.fromisoformat(window['end'])
    if first > last or last >= date.fromisoformat(summary['window_end']):
        raise ValueError('Only calendar-complete days are eligible')
    days = [(first + timedelta(days=i)).isoformat() for i in range((last-first).days+1)]
    selected = [g for g in summary['groups'] if first.isoformat() <= g['date_ct'] <= last.isoformat()]
    buckets = {stage: {'completed_requests': 0, 'logged_requests': 0, 'failed_requests': 0,
                       'other_status_requests': 0, 'tokens': {k: 0 for k in FIELDS},
                       'zero_write_cost_parts_usd': {}, 'cost_lower_usd': 0., 'cost_upper_usd': 0.,
                       'unreported_cache_write_groups': 0} for stage in STAGES}
    seen = set()
    for g in selected:
        key = (g['date_ct'], g['stage'], g['model'])
        if key in seen or g['stage'] not in STAGES:
            raise ValueError('Duplicate or unexpected group')
        seen.add(key)
        n = nonnegative(g['completed_requests'], 'completed', True)
        counts = {k: nonnegative(g[k], k, True) for k in
                  ('logged_requests', 'failed_requests', 'other_status_requests', 'completed_without_output_text')}
        if counts['logged_requests'] != n + counts['failed_requests'] + counts['other_status_requests']:
            raise ValueError('Inconsistent request counts')
        if counts['completed_without_output_text'] > n:
            raise ValueError('Outputless completion exceeds completed work')
        tokens, parts, low, high, unknown = price_group(g, config['rates'])
        b = buckets[g['stage']]
        # Charge all reported attempts; only output-bearing completions earn work credit.
        b['completed_requests'] += n - counts['completed_without_output_text']
        for k in ('logged_requests', 'failed_requests', 'other_status_requests'):
            b[k] += counts[k]
        for k, value in tokens.items():
            b['tokens'][k] += value
        for k, value in parts.items():
            b['zero_write_cost_parts_usd'][k] = b['zero_write_cost_parts_usd'].get(k, 0) + value
        b['cost_lower_usd'] += low
        b['cost_upper_usd'] += high
        b['unreported_cache_write_groups'] += int(unknown)
    for day in days:
        # An absent synthesis day is UNKNOWN: deterministic skip needs independent proof.
        if any(not any(k[0] == day and k[1] == stage for k in seen) for stage in STAGES):
            raise ValueError('Missing day/stage is unknown, not zero')
    refs = buckets[config['reference_stage']]['completed_requests']
    normalized = {}
    for stage, b in buckets.items():
        divisor = refs if stage == 'cross_camera' else b['completed_requests']
        if divisor <= 0:
            raise ValueError('No completed work for normalization')
        normalized[stage] = {k: b[k] / divisor for k in ('cost_lower_usd', 'cost_upper_usd')}
        normalized[stage]['zero_write_cost_parts_usd'] = {
            k: v/divisor for k, v in b['zero_write_cost_parts_usd'].items()}
    low = sum(v['cost_lower_usd'] for v in normalized.values())
    high = sum(v['cost_upper_usd'] for v in normalized.values())
    scale = lambda n: {'cost_lower_usd': low*n, 'cost_upper_usd': high*n}
    camera_calls = sum(buckets[s]['completed_requests'] for s in STAGES[:-1])
    return {
        'calendar_complete_days': days, 'reference_requests': refs,
        'completed_requests': sum(b['completed_requests'] for b in buckets.values()),
        'failed_requests': sum(b['failed_requests'] for b in buckets.values()),
        'other_status_requests': sum(b['other_status_requests'] for b in buckets.values()),
        'logged_requests': sum(b['logged_requests'] for b in buckets.values()),
        'reference_camera_work_ratio': camera_calls/(6*refs),
        'per_camera_work_ratios': {s: buckets[s]['completed_requests']/refs for s in STAGES[:-1]},
        'valid_six_camera_cycles': None, 'deduplicated_retries': None, 'latency': None,
        'coverage_limit': 'Request ratios are work diagnostics, not valid-cycle coverage or biological effectiveness.',
        'stages': buckets, 'six_camera_standardized_cost_per_reference_request': scale(1),
        'standardized_stage_costs_per_reference_request': normalized,
        'representative_dawn_window': scale(config['representative_dawn_reference_requests']),
        'representative_complete_day': scale(config['representative_complete_day_reference_requests']),
        'mean_logged_cost_per_calendar_complete_day': {
            k: sum(b[k] for b in buckets.values())/len(days) for k in ('cost_lower_usd', 'cost_upper_usd')},
        'daily_logged_costs': {day: {
            k: sum(price_group(g, config['rates'])[index] for g in selected if g['date_ct'] == day)
            for k, index in (('cost_lower_usd', 2), ('cost_upper_usd', 3))} for day in days},
    }


def savings_range(baseline, candidate):
    if baseline['cost_lower_usd'] <= 0:
        return None
    return {'percent_lower': 100*(1-candidate['cost_upper_usd']/baseline['cost_lower_usd']),
            'percent_upper': 100*(1-candidate['cost_lower_usd']/baseline['cost_upper_usd'])}


def build(summary, config):
    validate_config(config)
    if summary['status'] != 'available' or summary['invalid_records'] != 0:
        raise ValueError('Unavailable/invalid telemetry')
    baseline = period(summary, config, config['baseline'])
    post = period(summary, config, config['postdeployment'])
    # Hold synthesis workload constant as well as camera work for a second comparison.
    b_rate = baseline['stages']['cross_camera']['completed_requests']/baseline['reference_requests']
    p_rate = post['stages']['cross_camera']['completed_requests']/post['reference_requests']
    equal = copy.deepcopy(post['six_camera_standardized_cost_per_reference_request'])
    cross = post['standardized_stage_costs_per_reference_request']['cross_camera']
    for k in equal:
        equal[k] += cross[k]*(b_rate/p_rate-1)
    parts = {k: sum(s['zero_write_cost_parts_usd'][k] for s in
                   post['standardized_stage_costs_per_reference_request'].values())
             for k in ('ordinary_input', 'cached_input', 'cache_write', 'output_including_reasoning')}
    total = sum(parts.values())
    stage_shares = {s: sum(v['zero_write_cost_parts_usd'].values())/total for s, v in
                    post['standardized_stage_costs_per_reference_request'].items()}
    output_saving = sum(v['zero_write_cost_parts_usd']['output_including_reasoning']
                        for s, v in post['standardized_stage_costs_per_reference_request'].items()
                        if s != 'cross_camera') * config['candidate_camera_output_reduction_fraction']
    # Cache candidate is deliberately limited to one model with matching measured peer calls.
    boat = post['stages']['camera:montrose_pier_boat']
    peers = [post['stages']['camera:' + c] for c in ('montrose_pier_bird', 'montrose_shoreline')]
    target = min(p['tokens']['cached_input_tokens']/p['completed_requests'] for p in peers)
    extra = max(0, target - boat['tokens']['cached_input_tokens']/boat['completed_requests'])
    models = {g['model'] for g in summary['groups'] if config['postdeployment']['start'] <= g['date_ct'] <= config['postdeployment']['end']}
    cache_candidate = None
    if len(models) == 1:
        rate = config['rates'][next(iter(models))]
        extra = min(extra, (boat['tokens']['input_tokens']-boat['tokens']['cached_input_tokens'])/boat['completed_requests'])
        cache_candidate = {
            'extra_cache_read_tokens_per_boat_call': extra,
            'gross_savings_usd_per_reference_request': extra*(rate['input_per_million']-rate['cached_input_per_million'])/1e6,
            'net_savings_usd_lower_per_reference_request': extra*(rate['input_per_million']-rate['cached_input_per_million']-rate['cache_write_per_million'])/1e6,
            'assumption': 'Peer cache rate is attainable without prompt/coverage changes; net lower conservatively charges one additional write of extra input per extra read. Not demonstrated.'}
    candidate_scale = lambda value: {
        'per_reference_request_usd': value,
        'representative_dawn_usd': value*config['representative_dawn_reference_requests'],
        'representative_complete_day_usd': value*config['representative_complete_day_reference_requests']}
    if cache_candidate:
        cache_candidate['gross_savings'] = candidate_scale(cache_candidate['gross_savings_usd_per_reference_request'])
        cache_candidate['net_lower_savings'] = candidate_scale(cache_candidate['net_savings_usd_lower_per_reference_request'])
    return {
        'schema_version': 1, 'status': 'RESEARCH_ONLY_CONDITIONAL_LIST_PRICE_ACCOUNTING',
        'baseline': baseline, 'postdeployment': post, 'pricing_assumptions': config,
        'savings_percent_at_observed_synthesis_rate': savings_range(baseline['six_camera_standardized_cost_per_reference_request'], post['six_camera_standardized_cost_per_reference_request']),
        'post_cost_at_baseline_synthesis_call_rate': equal,
        'savings_percent_at_equal_camera_and_synthesis_work': savings_range(baseline['six_camera_standardized_cost_per_reference_request'], equal),
        'zero_write_scenario_cost_parts_per_reference_request_usd': parts,
        'zero_write_scenario_stage_cost_shares': stage_shares,
        'candidates': {
            'camera_output_reduction': {'assumed_fraction': config['candidate_camera_output_reduction_fraction'],
                'savings_usd_per_reference_request': output_saving, 'savings_percent_of_zero_write_scenario': output_saving/total*100,
                'savings': candidate_scale(output_saving),
                'gate': 'Held-out event/non-event effectiveness, UNKNOWN and alligator safety equivalence required before any output change.'},
            'boat_cache_peer_rate': cache_candidate,
            'eliminate_all_synthesis_theoretical_ceiling': {'cost_share': stage_shares['cross_camera'],
                'gate': 'Not recommended. Ambiguous and low-light UNKNOWN cycles require synthesis; ceiling is not attainable evidence.'}},
        'limits': ['Not actual account spend; rates and service conditions are explicit assumptions.',
            'Cache-write bounds assume ordinary input + cache reads + cache writes partition reported input.',
            'Dawn/day costs extrapolate period-average mix to fixed completed work, not time-resolved observed costs.',
            'Text versus image input and visible output versus reasoning costs are not separately identified by these aggregates.',
            'Cost efficiency does not establish equivalent event detection; 50% target is not demonstrated.'],
        'production_changes': [],
        'preserved': ['six cameras and capture coverage', 'UNKNOWN semantics', '9 PM reporting gate',
                      'probabilities', 'weights', 'thresholds', 'forecasts', 'alerts'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usage', type=Path, default=HERE/'usage_20261002.json')
    parser.add_argument('--pricing', type=Path, default=HERE/'pricing_assumptions.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.usage.read_bytes()
    pricing_raw = args.pricing.read_bytes()
    report = build(json.loads(raw), json.loads(pricing_raw))
    report['source'] = {'usage_sha256': hashlib.sha256(raw).hexdigest(),
                        'usage_git_blob_sha': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                        'pricing_sha256': hashlib.sha256(pricing_raw).hexdigest(),
                        'audit_reference_commit': 'f2ae704bd79205852efa895875b3eaf625981ca9'}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()

"""Read-only, local-log J18 research export. Never infer capture joins from time."""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

UNKNOWN = 'UNKNOWN'
CAMERAS = ('montrose_pier_boat', 'montrose_pier_bird', 'montrose_shoreline',
           'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth')
TOKENS = ('input_tokens', 'cached_input_tokens', 'output_tokens',
          'reasoning_output_tokens', 'total_tokens', 'cache_write_tokens')
TZ = ZoneInfo('America/Chicago')


def count(value):
    if value is None or value == UNKNOWN:
        return None
    if type(value) is not int or value < 0:
        raise ValueError('Invalid token count')
    return value


def digest(value):
    return hashlib.sha256(value).hexdigest()


def pseudonym(key, kind, value):
    if len(key) < 32:
        raise ValueError('Use a private random key of at least 32 bytes')
    return hmac.new(key, (kind + ':' + str(value)).encode(), hashlib.sha256).hexdigest()


def export(raw, key, manifests=()):
    """Manifest join is permitted only on a capture_id explicitly in usage.

    Manifests are local canonical capture receipts with capture_id, cameras,
    runtime_version and capture_time_ct. Current legacy usage has no capture_id.
    Public output exposes keyed pseudonyms, no provider/private IDs or text.
    """
    index = {}
    for payload in manifests:
        m = json.loads(payload)
        cid = m['capture_id']
        if cid in index:
            raise ValueError('Duplicate canonical capture receipt')
        index[cid] = (m, digest(payload))
    rows, invalid, seen = [], 0, set()
    for line in raw.splitlines():
        try:
            r = json.loads(line)
            stage = r['stage']
            if stage not in ('cross_camera',) + tuple('camera:' + c for c in CAMERAS):
                raise ValueError('Unexpected stage')
            when = datetime.fromisoformat(r['recorded_at_ct'])
            if when.tzinfo is None:
                raise ValueError('Timezone required')
            when = when.astimezone(TZ)
            tokens = {f: count(r.get(f)) for f in TOKENS}
            for subset, parent in (('cached_input_tokens', 'input_tokens'),
                                   ('reasoning_output_tokens', 'output_tokens')):
                if tokens[subset] is not None and tokens[parent] is not None and tokens[subset] > tokens[parent]:
                    raise ValueError('Invalid token subset')
            if all(tokens[f] is not None for f in ('input_tokens', 'output_tokens', 'total_tokens')):
                if tokens['total_tokens'] != tokens['input_tokens'] + tokens['output_tokens']:
                    raise ValueError('Invalid total')
            # A provider cache-write number without its billing semantics is
            # retained as reported telemetry, but cannot be priced as a partition.
            write_semantics = r.get('cache_write_semantics')
            if write_semantics != 'partition_of_input':
                write_semantics = UNKNOWN
            if write_semantics == 'partition_of_input' and all(tokens[f] is not None for f in ('input_tokens', 'cached_input_tokens', 'cache_write_tokens')):
                if tokens['cached_input_tokens'] + tokens['cache_write_tokens'] > tokens['input_tokens']:
                    raise ValueError('Writes exceed input partition')
            line_sha = digest(line)
            identity = r.get('attempt_id') or r.get('response_id') or r.get('request_id') or line_sha
            attempt = pseudonym(key, 'attempt', identity)
            if attempt in seen:
                raise ValueError('Duplicate attempt; no silently dropped charges')
            seen.add(attempt)
            binding, integrity, runtime, capture_time = UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN
            manifest_sha = UNKNOWN
            if r.get('telemetry_schema_version') == 1:
                v = r.get('runtime_version')
                if isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,100}', v):
                    runtime = v
            cid = r.get('capture_id')
            if cid is not None and cid in index:
                m, manifest_sha = index[cid]
                binding = pseudonym(key, 'capture', cid)
                cams = m.get('cameras', {})
                selected = CAMERAS if stage == 'cross_camera' else (stage.split(':', 1)[1],)
                states = []
                for camera in selected:
                    c = cams.get(camera, {})
                    ok = c.get('capture_ok')
                    issues = c.get('integrity_issues')
                    states.append(False if ok is False or (isinstance(issues, list) and issues)
                                  else True if ok is True and issues == [] else UNKNOWN)
                integrity = False if False in states else True if all(s is True for s in states) else UNKNOWN
                # Runtime must be stamped on this receipt, not the current file.
                v = m.get('runtime_version')
                if isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,100}', v):
                    runtime = v
                ct = m.get('capture_time_ct')
                if ct:
                    dt = datetime.fromisoformat(ct)
                    if dt.tzinfo is None:
                        raise ValueError('Naive capture time')
                    capture_time = dt.astimezone(TZ).isoformat()
            status = r.get('status')
            if status not in ('completed', 'request_failed', 'failed', 'incomplete', 'cancelled', 'queued', 'in_progress'):
                status = UNKNOWN
            tier = r.get('actual_service_tier') if r.get('telemetry_schema_version') == 1 else r.get('billed_service_tier')
            tier = tier if tier in ('default', 'standard', 'flex', 'priority', 'scale', 'fast') else UNKNOWN
            context = r.get('billing_context_class')
            context = context if context in ('short', 'long') else UNKNOWN
            model = r.get('model')
            model = model if model == 'gpt-5.6-luna' else UNKNOWN
            prefix = r.get('prompt_prefix_sha256')
            prefix = pseudonym(key, 'prefix', prefix) if isinstance(prefix, str) and re.fullmatch('[0-9a-f]{64}', prefix) else UNKNOWN
            rows.append(dict(attempt_key=attempt, capture_key=binding,
                source_line_key=pseudonym(key, 'line', line_sha), manifest_sha256=manifest_sha,
                recorded_at_ct=when.isoformat(), capture_time_ct=capture_time,
                date_ct=when.date().isoformat(),
                time_bin_ct='04-08' if 4 <= when.hour < 8 else '08-20' if 8 <= when.hour < 20 else '20-04',
                stage=stage, model=model, status=status,
                output_text_present=r.get('output_text_present') if type(r.get('output_text_present')) is bool else UNKNOWN,
                camera_integrity=integrity, runtime_version=runtime,
                service_tier=tier, context_class=context, prefix_key=prefix,
                cache_write_semantics=write_semantics, tokens=tokens))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            invalid += 1
    return dict(schema_version=1, status='RESEARCH_ONLY', rows=rows,
                invalid_records=invalid, source_sha256=digest(raw),
                timezone='America/Chicago', production_changes=[])


def diagnose(data):
    cohorts = defaultdict(list)
    dimensions = ('date_ct', 'stage', 'model', 'runtime_version', 'service_tier',
                  'context_class', 'time_bin_ct', 'prefix_key')
    for r in data['rows']:
        cohorts[tuple(r[f] for f in dimensions)].append(r)
    groups = []
    for key, rows in sorted(cohorts.items()):
        totals = {f: dict(known_sum=sum(r['tokens'][f] or 0 for r in rows),
                          missing_records=sum(r['tokens'][f] is None for r in rows)) for f in TOKENS}
        i, c = totals['input_tokens'], totals['cached_input_tokens']
        ratio = c['known_sum'] / i['known_sum'] if i['known_sum'] and not i['missing_records'] and not c['missing_records'] else UNKNOWN
        groups.append(dict(zip(dimensions, key), attempts=len(rows), tokens=totals,
                           cache_read_fraction=ratio))
    missing = {f: sum(r[f] == UNKNOWN for r in data['rows']) for f in
               ('capture_key', 'camera_integrity', 'runtime_version', 'service_tier',
                'context_class', 'prefix_key', 'cache_write_semantics')}
    return dict(schema_version=1, status='RESEARCH_ONLY_MEASUREMENT', attempts=len(data['rows']),
                invalid_records=data['invalid_records'], unknown_records=missing, cohorts=groups,
                valid_cycle_cost=UNKNOWN, observed_dawn_cost=UNKNOWN, account_spend=UNKNOWN,
                limits=['Cache-read fractions do not establish identical-prefix reuse or explain misses.',
                        'No timestamp-only capture joins; all retries and failures remain chargeable.',
                        'No billed rates or cache-write semantics are inferred from counts.',
                        '04-08 is a fixed Central clock bin, not an astronomical dawn window.'],
                source_sha256=data['source_sha256'], production_changes=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usage', type=Path, required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--manifest', type=Path, action='append', default=[])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    data = export(a.usage.read_bytes(), a.key_file.read_bytes(), [m.read_bytes() for m in a.manifest])
    a.output.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    a.report.write_text(json.dumps(diagnose(data), indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

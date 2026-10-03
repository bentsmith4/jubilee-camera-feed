"""Reproduce an evidence receipt; raw desktop logs remain local."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import measurement
import validate_compression as v

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usage', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--export', type=Path, required=True)
    a = p.parse_args()
    # Fresh private pseudonym key is neither published nor passed on a command line.
    data = measurement.export(a.usage.read_bytes(), os.urandom(32))
    a.export.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    report = measurement.diagnose(data)
    report['recorded_time_range_ct'] = [min(r['recorded_at_ct'] for r in data['rows']), max(r['recorded_at_ct'] for r in data['rows'])] if data['rows'] else []
    report['cache_write_missing_records'] = sum(r['tokens']['cache_write_tokens'] is None for r in data['rows'])
    report['completed_attempts'] = sum(r['status']=='completed' and r['output_text_present'] is True for r in data['rows'])
    report['failed_attempts'] = sum(r['status'] in ('failed', 'request_failed') for r in data['rows'])
    report['other_attempts'] = len(data['rows']) - report['completed_attempts'] - report['failed_attempts']
    fixture = ROOT/'tests/fixtures/vision_quiet_low_detectability_20260927.json'
    obj = json.loads(fixture.read_text())
    pretty = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False).encode()
    compact = v.compact(obj).encode()
    report['serialization_diagnostic'] = dict(source_path=str(fixture.relative_to(ROOT)).replace('\\','/'),
        source_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        pretty_utf8_bytes=len(pretty), compact_utf8_bytes=len(compact),
        byte_reduction_fraction=1-len(compact)/len(pretty), fields_roundtrip_exactly=json.loads(compact)==obj,
        billed_token_savings='UNKNOWN', event_sensitivity_change='UNKNOWN',
        false_alert_change='UNKNOWN', unknown_behavior_change='UNKNOWN', safety_behavior_change='UNKNOWN',
        limit='Existing low-light model-output regression fixture; not independent biological labels or an API replay.')
    report['compression_validation'] = v.evaluate(json.loads((HERE/'held_out_cases.json').read_text()),
        json.loads((HERE/'protocol.json').read_text()),
        json.loads((HERE.parent/'j18_cost_accounting/pricing_assumptions.json').read_text()))
    report['telemetry_gap'] = dict(current_runtime_source='desktop_runtime/analyze_frames.py',
        runtime_source_git_blob='668cf263984d1aa7b843fe363a5bdb93e8e89839',
        required_prospective_fields=['explicit capture_id on each API attempt',
            'canonical capture receipt and integrity flags', 'runtime version on that capture receipt',
            'actual response/billing service tier', 'billing context class backed by account rules',
            'cache-write count and documented billing semantics if provided',
            'stable-prefix fingerprint, cache options and attempt timing if provided'],
        note='Exporter does not change runtime logging. Existing records cannot retrospectively recover these fields.')
    a.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__': main()

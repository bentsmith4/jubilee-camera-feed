import base64
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop_runtime'))
from attempt_telemetry import attempt_fields, capture_context, bind_integrity, sha, UNKNOWN
from model_data.j18_measurement.readback_telemetry import readback
from model_data.j18_measurement.measurement import export


class AttemptTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.status = json.dumps({'capture_time_ct':'2026-10-03T06:00:00-05:00'}).encode()
        self.burst = self.status
        self.context = capture_context(self.status, self.burst)
        self.kwargs = dict(model='gpt-5.6-luna', service_tier='priority',
            prompt_cache_options={'mode':'explicit', 'ttl':'30m'},
            input=[{'role':'developer','content':[{'type':'input_text','text':'PRIVATE PREFIX',
                'prompt_cache_breakpoint':{'mode':'explicit'}}]},
                {'role':'user','content':[{'type':'input_image',
                    'image_url':'data:image/jpeg;base64,'+base64.b64encode(b'PRIVATE IMAGE').decode()}]}])
        self.response = NS(model='gpt-5.6-luna', service_tier='default',
            usage=NS(input_tokens_details=NS(cache_write_tokens=40)))

    def row(self, response=None):
        r = attempt_fields(response or self.response, self.kwargs, 'runtime-test-v1', self.context)
        return dict(r, stage='camera:montrose_pier_boat', recorded_at_ct='2026-10-03T06:00:10-05:00',
            status='completed', model='gpt-5.6-luna', input_tokens=100, output_tokens=20,
            total_tokens=120, cached_input_tokens=10, reasoning_output_tokens=0)

    def snapshot(self):
        return dict(generated_from_capture_time_ct=self.context['capture_id'],
            input_hashes=dict(self.context['capture_input_hashes']), cells=[{'camera_rows':[
                dict(camera_id='montrose_pier_boat', capture_ok=True, integrity_issues=[])]}])

    def test_returned_tier_and_writes_only(self):
        r = self.row()
        self.assertEqual(r['actual_service_tier'], 'default')
        self.assertEqual(r['requested_service_tier'], 'priority')
        self.assertEqual(r['cache_write_tokens'], 40)
        self.assertEqual(r['cache_write_semantics'], 'partition_of_input')
        self.assertEqual(r['billing_context_class'], UNKNOWN)
        self.assertEqual(r['billed_service_tier'], UNKNOWN)
        self.assertEqual(r['input_image_sha256'], [sha(b'PRIVATE IMAGE')])
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_missing_and_zero_distinct(self):
        r = self.row(NS())
        self.assertEqual(r['cache_write_tokens'], UNKNOWN)
        self.assertEqual(r['actual_service_tier'], UNKNOWN)
        self.response.usage.input_tokens_details.cache_write_tokens = 0
        self.assertEqual(self.row()['cache_write_tokens'], 0)

    def test_unknown_model_semantics_not_guessed(self):
        self.response.model = 'other'
        self.assertEqual(self.row()['cache_write_tokens'], 40)
        self.assertEqual(self.row()['cache_write_semantics'], UNKNOWN)

    def test_stable_prefix_only_and_breakpoint_identity(self):
        before = self.row()['prompt_prefix_sha256']
        self.kwargs['input'][1]['content'] = [{'type':'input_text', 'text':'CHANGED SUFFIX'}]
        self.assertEqual(self.row()['prompt_prefix_sha256'], before)
        self.kwargs['input'][0]['content'][0]['prompt_cache_breakpoint'] = {'mode':'implicit'}
        self.assertNotEqual(self.row()['prompt_prefix_sha256'], before)

    def test_capture_mismatch_stays_unknown(self):
        self.assertEqual(capture_context(self.status, b'{"capture_time_ct":"OTHER"}'), {})
        self.assertEqual(attempt_fields(None, {}, 'v1', {})['capture_id'], UNKNOWN)

    def test_canonical_exact_readback_and_integrity_failure(self):
        row, snap = self.row(), self.snapshot()
        raw = json.dumps(row).encode()
        receipt = json.dumps(snap).encode()
        self.assertTrue(readback(raw, [receipt])['rows'][0]['camera_integrity'])
        snap['cells'][0]['camera_rows'][0]['integrity_issues'] = ['STALE']
        self.assertFalse(bind_integrity(row, snap, json.dumps(snap).encode())['camera_integrity'])
        snap['input_hashes']['status.json'] = 'wrong'
        self.assertEqual(bind_integrity(row, snap, json.dumps(snap).encode())['camera_integrity'], UNKNOWN)
        self.assertEqual(readback(raw, [])['matched_attempts'], 0)
        self.assertEqual(readback(raw, [receipt, receipt])['matched_attempts'], 0)

    def test_synthesis_needs_six_camera_receipts(self):
        row, snap = self.row(), self.snapshot()
        row['stage'] = 'cross_camera'
        self.assertEqual(bind_integrity(row, snap, json.dumps(snap).encode())['camera_integrity'], UNKNOWN)

    def test_sdk_call_and_failure_readback(self):
        from test_vision_efficiency import NEW
        from unittest.mock import Mock, patch
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.object(NEW, 'require_season'), patch.object(NEW, 'TELEMETRY_CONTEXT', self.context), patch.object(NEW, 'API_USAGE_PATH', Path(directory)/'usage.jsonl'):
            response = NS(id='response', _request_id='request', status='completed',
                output_text='PRIVATE OUTPUT', model='gpt-5.6-luna', service_tier='default',
                usage=NS(input_tokens=100, output_tokens=20, total_tokens=120,
                    input_tokens_details=NS(cached_tokens=10, cache_write_tokens=40)))
            create = Mock(return_value=response)
            with patch.object(NEW, 'client', NS(responses=NS(create=create))):
                self.assertIs(NEW.api_response('camera:montrose_pier_boat', **self.kwargs), response)
                create.assert_called_once_with(**self.kwargs)
                error = RuntimeError('PRIVATE ERROR')
                create.side_effect = error
                with self.assertRaises(RuntimeError) as caught:
                    NEW.api_response('camera:montrose_pier_boat', **self.kwargs)
                self.assertIs(caught.exception, error)
            raw = NEW.API_USAGE_PATH.read_bytes()
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0]['attempt_id'], rows[1]['attempt_id'])
            self.assertEqual(rows[1]['status'], 'request_failed')
            self.assertEqual(rows[1]['actual_service_tier'], UNKNOWN)
            self.assertNotIn(b'PRIVATE', raw)
            result = readback(raw, [json.dumps(self.snapshot()).encode()])
            self.assertEqual(result['matched_attempts'], 2)

    def test_export_retains_unknown_and_each_invocation(self):
        row = self.row(NS())
        other = dict(row, attempt_id='distinct-retry', response_id='same-response')
        row['response_id'] = 'same-response'
        raw = '\n'.join(json.dumps(x) for x in (row, other)).encode()
        result = export(raw, b'x'*32)
        self.assertEqual(result['invalid_records'], 0)
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual(result['rows'][0]['runtime_version'], 'runtime-test-v1')
        self.assertEqual(result['rows'][0]['tokens']['cache_write_tokens'], None)


if __name__ == '__main__':
    unittest.main()

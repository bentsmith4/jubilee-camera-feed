import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop_runtime'))
import json
import tempfile
import unittest
from datetime import datetime, timezone
import publish_github as p

class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / 'frames').mkdir()
        self.now = datetime(2026, 9, 8, 16, tzinfo=timezone.utc)

    def row(self, **changes):
        row = dict(recorded_at_ct='2026-09-08T10:10:00-05:00', stage='cross_camera',
                   model='gpt-5.6-luna', status='completed', output_text_present=True,
                   input_tokens=100, output_tokens=20, total_tokens=120,
                   cached_input_tokens=40, reasoning_output_tokens=10)
        row.update(changes)
        return row

    def write(self, rows):
        (self.base/'frames/api_usage.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def test_aggregates_subsets_without_double_counting_and_strips_private_fields(self):
        row = self.row(request_id='SECRET', response_id='SECRET', prompt='SECRET', image='SECRET')
        self.write([row, row])
        result = p.usage_summary(self.base, self.now)
        group = result['groups'][0]
        self.assertEqual(group['logged_requests'], 2)
        self.assertEqual(group['tokens']['total_tokens']['known_sum'], 240)
        self.assertEqual(group['tokens']['cached_input_tokens']['known_sum'], 80)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertIsNone(result['retry_count'])

    def test_missing_usage_not_zero_cost(self):
        self.write([self.row(status='request_failed', **{f:None for f in ('input_tokens','output_tokens','total_tokens','cached_input_tokens','reasoning_output_tokens')})])
        group = p.usage_summary(self.base,self.now)['groups'][0]
        self.assertEqual(group['failed_requests'],1)
        self.assertEqual(group['tokens']['total_tokens']['missing_records'],1)

    def test_central_dates_and_window(self):
        self.write([self.row(recorded_at_ct='2026-09-08T01:00:00+00:00'),
                    self.row(recorded_at_ct='2026-07-01T01:00:00+00:00')])
        result = p.usage_summary(self.base,self.now)
        self.assertEqual(result['groups'][0]['date_ct'],'2026-09-07')
        self.assertEqual(result['excluded_outside_window'],1)

    def test_malformed_unknown_and_future_do_not_poison_valid_rows(self):
        self.write([self.row(), {}, self.row(stage='SECRET'), self.row(input_tokens=-1),
                    self.row(cached_input_tokens=101),self.row(total_tokens=999),
                    self.row(recorded_at_ct='2027-01-01T00:00:00+00:00')])
        with (self.base/'frames/api_usage.jsonl').open('a') as f: f.write('{partial')
        result=p.usage_summary(self.base,self.now)
        self.assertEqual(result['invalid_records'],7)
        self.assertEqual(result['groups'][0]['logged_requests'],1)
        self.assertNotIn('SECRET',json.dumps(result))

    def test_missing_file_explicitly_unavailable(self):
        result=json.loads(p.usage_payload(self.base))
        self.assertEqual(result['status'],'unavailable')

    def test_unrecognized_model_redacted_but_usage_kept(self):
        self.write([self.row(model='SECRET')])
        result=p.usage_summary(self.base,self.now)
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertEqual(result['groups'][0]['model'],'unrecognized_or_unavailable')

    def test_camera_publication_includes_summary_when_logging_missing(self):
        stamp=datetime.now(timezone.utc).isoformat()
        for name in p.METADATA:
            (self.base/'frames'/name).write_text(json.dumps({'capture_time_ct':stamp,'cameras':{}}))
        files,_=p.payload(self.base)
        self.assertEqual(json.loads(files['api_usage_summary.json'])['status'],'unavailable')

if __name__=='__main__':unittest.main()

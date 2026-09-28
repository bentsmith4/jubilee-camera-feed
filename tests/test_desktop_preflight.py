"""Run the real PowerShell entry point with offline Task Scheduler fixtures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_desktop_verifier import Fixture, fingerprints


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell exercised by the Windows CI job')
class PreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.f = Fixture(Path(temp.name))

    def run_wrapper(self, task_error=False, python=None):
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        wrapper = Path(__file__).resolve().parents[1] / 'tools' / 'desktop_preflight.ps1'
        root = str(self.f.root)
        # Time relative to fixture won't be fresh on CI, but acceptance must still
        # report every domain and correctly distinguish failures from missing R2.
        code = r'''
function Get-ScheduledTask {
    [pscustomobject]@{
        TaskName='Jubilee Live Cameras'; TaskPath='\'; State='Running'
        Settings=[pscustomobject]@{Enabled=$true}
        Principal=[pscustomobject]@{UserId='SENTINEL_ACCOUNT_SECRET'}
        Actions=@([pscustomobject]@{Execute='C:\Python\python.exe'; Arguments='"ROOT\live_loop.py"'; WorkingDirectory='ROOT'})
    }
}
function Get-ScheduledTaskInfo {
    [pscustomobject]@{LastRunTime=[datetime]'2026-09-27T06:00:00Z'; LastTaskResult=267009; NumberOfMissedRuns=0}
}
'''.replace('ROOT', root.replace("'", "''"))
        if task_error:
            code += "function Get-ScheduledTaskInfo { throw 'SENTINEL_TASK_SECRET' }\n"
        code += '& ' + quote(wrapper) + ' -Root ' + quote(root) + ' -Python ' + quote(python or sys.executable) + ' -Offline'
        # -Command otherwise reduces a called script's nonzero exit to 1.
        # Preserve the same exact exit code a direct -File invocation returns.
        code += '; exit $LASTEXITCODE'
        return subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], capture_output=True, text=True, timeout=30)

    def test_wrapper_emits_one_sanitized_report_without_file_writes(self):
        before = fingerprints(self.f.root)
        proc = self.run_wrapper()
        report = json.loads(proc.stdout)
        self.assertIn(proc.returncode, (1, 2))
        self.assertEqual(proc.stderr, '')
        self.assertEqual(report['schema_version'], '3.0')
        self.assertEqual(len(report['cameras']), 6)
        if sys.platform == 'win32':
            self.assertNotIn(report['checks']['scheduled_tasks']['code'],
                             ('coordinator_definition_mismatch', 'task_inventory_unavailable'))
        self.assertNotIn('SENTINEL', proc.stdout)
        self.assertNotIn(str(self.f.root), proc.stdout)
        self.assertEqual(fingerprints(self.f.root), before)

    def test_task_api_failure_is_sanitized(self):
        proc = self.run_wrapper(task_error=True)
        report = json.loads(proc.stdout)
        self.assertEqual(report['checks']['scheduled_tasks']['code'], 'task_inventory_unavailable')
        self.assertNotIn('SENTINEL', proc.stdout + proc.stderr)

    def test_missing_python_is_sanitized(self):
        proc = self.run_wrapper(python='missing-SENTINEL-interpreter')
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)['code'], 'verifier_unavailable')
        self.assertNotIn('SENTINEL', proc.stdout + proc.stderr)


if __name__ == '__main__':
    unittest.main()

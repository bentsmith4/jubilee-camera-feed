"""Offline seasonal boundary and no-paid-call checks."""
import ast
import runpy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import time
import json

ROOT = Path(__file__).resolve().parents[1] / "desktop_runtime"
sys.path.insert(0, str(ROOT))
import seasonal_policy as season

class SeasonalTests(unittest.TestCase):
    def test_all_dates_in_ordinary_and_leap_years(self):
        for year in (2026, 2028, 2032):
            d = datetime(year, 1, 1, 12, tzinfo=season.TZ)
            while d.year == year:
                expected = datetime(year, 5, 18, tzinfo=season.TZ) <= d < datetime(year, 11, 15, tzinfo=season.TZ)
                self.assertEqual(season.in_season(d), expected, d)
                d += timedelta(days=1)

    def test_local_midnight_and_naive_rejection(self):
        for stamp, expected in [("2026-05-18T04:59:00+00:00", False), ("2026-05-18T05:00:00+00:00", True), ("2026-11-15T05:59:00+00:00", True), ("2026-11-15T06:00:00+00:00", False)]:
            self.assertEqual(season.in_season(datetime.fromisoformat(stamp)), expected)
        with self.assertRaises(ValueError):
            season.in_season(datetime(2026, 1, 18))

    def test_offseason_scripts_exit_before_capture_or_dependencies(self):
        with patch.object(season, "in_season", return_value=False):
            for script in ("analyze_frames.py", "capture_publish.py"):
                with self.assertRaises(SystemExit) as result:
                    runpy.run_path(str(ROOT / script), run_name="__main__")
                self.assertEqual(result.exception.code, 0)

    def test_offseason_api_wrapper_never_calls_client(self):
        module = ast.parse((ROOT / "analyze_frames.py").read_text())
        func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "api_response")
        calls = []
        env = dict(time=time, json=json, datetime=datetime, TZ=season.TZ,
                   require_season=season.require_season,
                   API_USAGE_PATH=Path("/nonexistent/season-test/usage"),
                   client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs))))
        exec(compile(ast.Module(body=[func], type_ignores=[]), "<api_wrapper>", "exec"), env)
        with patch.object(season, "in_season", return_value=False):
            with self.assertRaises(SystemExit):
                env["api_response"]("test", model="unused")
        self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()

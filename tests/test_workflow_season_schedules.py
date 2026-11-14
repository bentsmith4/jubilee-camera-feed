"""UTC cron slices preserve the exact Central production season and cadence."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
CT = ZoneInfo("America/Chicago")
WORKFLOWS = {
    "asos_weather.yml": lambda d: d.minute == 7,
    "current_state_freshness.yml": lambda d: d.minute in (17, 47),
    "observation_logging.yml": lambda d: d.minute == 17,
    "arcos_realtime.yml": lambda d: d.minute in (5, 35),
    "sensing_quality.yml": lambda d: d.minute == 37 and d.hour % 3 == 0,
}


def values(field, maximum, minimum=0):
    result = set()
    for item in field.split(","):
        if item == "*":
            result.update(range(minimum, maximum + 1))
        elif item.startswith("*/"):
            result.update(range(minimum, maximum + 1, int(item[2:])))
        elif "-" in item:
            start, end = map(int, item.split("-"))
            result.update(range(start, end + 1))
        else:
            result.add(int(item))
    return result


def cron_rows(path):
    rows = re.findall(r"- cron: '([^']+)'", path.read_text())
    parsed = []
    for row in rows:
        minute, hour, day, month, weekday = row.split()
        if weekday != "*":
            raise AssertionError(f"unexpected weekday constraint: {row}")
        parsed.append((values(minute, 59), values(hour, 23),
                       values(day, 31, 1), values(month, 12, 1)))
    return parsed


def matches(dt, rows):
    return any(dt.minute in minute and dt.hour in hour and
               dt.day in day and dt.month in month
               for minute, hour, day, month in rows)


def in_season(dt):
    local = dt.astimezone(CT)
    return (5, 18) <= (local.month, local.day) <= (11, 14)


class WorkflowSeasonSchedules(unittest.TestCase):
    def test_utc_slices_equal_original_inseason_cadence(self):
        for year in (2026, 2028):
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            for name, cadence in WORKFLOWS.items():
                rows = cron_rows(ROOT / ".github/workflows" / name)
                actual, expected = set(), set()
                now = start
                while now < end:
                    if matches(now, rows):
                        actual.add(now)
                    if in_season(now) and cadence(now):
                        expected.add(now)
                    now += timedelta(minutes=1)
                self.assertEqual(actual, expected, (year, name))

    def test_code_validation_manual_paths_and_weekly_science_remain(self):
        for name in WORKFLOWS:
            text = (ROOT / ".github/workflows" / name).read_text()
            self.assertIn("push:", text)
        for name in ("asos_weather.yml", "sensing_quality.yml", "current_state_freshness.yml",
                     "observation_logging.yml", "arcos_realtime.yml"):
            self.assertIn("workflow_dispatch:", (ROOT / ".github/workflows" / name).read_text())
        water = (ROOT / ".github/workflows/water_quality_ingest.yml").read_text()
        self.assertIn("cron: '17 11 * * 2'", water)

    def test_obsolete_first_dawn_subscriptions_are_retired(self):
        workflows = ROOT / ".github/workflows"
        self.assertFalse((workflows / "first_dawn_acceptance.yml").exists())
        self.assertFalse((workflows / "pr34_dawn_followup.yml").exists())
        # Historical tools, fixtures and terminal-receipt parsers remain.
        self.assertTrue((ROOT / "tools/first_dawn_acceptance.py").exists())
        self.assertTrue((ROOT / "tools/pr34_dawn_followup.py").exists())


if __name__ == "__main__":
    unittest.main()

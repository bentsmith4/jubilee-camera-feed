"""Append-only, allowlisted camera publication; never edits the working tree."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import re

BASE = Path(r'C:\JubileeCams')
from camera_policy import CAMERA_IDS as CAMERAS
METADATA = ('status.json', 'vision.json', 'burst_status.json')

def git(repo, *args, env=None, data=None, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], input=data,
                            capture_output=True, env=env)
    if check and result.returncode:
        raise RuntimeError('Git operation failed: ' + args[0] + ' (diagnostics suppressed)')
    return result

def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt

def validate_private(value):
    if isinstance(value, dict):
        if isinstance(value.get('cameras'), dict) and set(value['cameras']) - set(CAMERAS):
            raise ValueError('Unapproved camera metadata: publication refused')
        for key, item in value.items():
            if key.lower() in {'device_id', 'resource_name', 'access_token', 'refresh_token', 'answersdp', 'offersdp'}:
                raise ValueError('Private metadata: publication refused')
            validate_private(item)
    elif isinstance(value, list):
        for item in value:
            validate_private(item)
    elif isinstance(value, str) and any(x in value.lower() for x in ('rtsp://', 'rtsps://', 'bearer ', 'streamextensiontoken', '/enterprises/')):
        raise ValueError('Private stream data: publication refused')


def usage_summary(base, now=None):
    """Publish only allowlisted daily aggregates; never raw telemetry fields."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("America/Chicago")).date()
    first = today - timedelta(days=30)
    result = {
        "schema_version": 1,
        "generated_at_utc": now.isoformat(),
        "timezone": "America/Chicago",
        "window_start": first.isoformat(),
        "window_end": today.isoformat(),
        "status": "available",
        "billing_status": "unpriced_token_usage_not_actual_spend",
        "coverage": "logged_requests_only; missing_days_are_not_zero; current_day_is_partial",
        "cycle_coverage": "not_inferred_from_request_counts; inspect_camera_status_separately",
        "retry_count": None,
        "invalid_records": 0,
        "excluded_outside_window": 0,
        "groups": [],
    }
    groups = {}
    stages = {"camera:" + camera for camera in CAMERAS} | {"cross_camera"}
    fields = ("input_tokens", "output_tokens", "total_tokens",
              "cached_input_tokens", "reasoning_output_tokens")
    with (base / "frames" / "api_usage.jsonl").open(encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                dt = timestamp(row["recorded_at_ct"])
                if dt > now + timedelta(minutes=2):
                    raise ValueError("Future telemetry")
                day = dt.astimezone(ZoneInfo("America/Chicago")).date()
                if not first <= day <= today:
                    result["excluded_outside_window"] += 1
                    continue
                stage = row["stage"]
                if stage not in stages:
                    raise ValueError("Unknown stage")
                model = row.get("model")
                # Do not copy arbitrary strings from local logs into a public file.
                if not isinstance(model, str) or not re.fullmatch(r"gpt-5[.]6-luna(?:-\d{4}-\d{2}-\d{2})?", model):
                    model = "unrecognized_or_unavailable"
                values = {}
                for field in fields:
                    value = row.get(field)
                    if value is not None and (type(value) is not int or value < 0):
                        raise ValueError("Invalid token count")
                    values[field] = value
                for subset, total in (("cached_input_tokens", "input_tokens"),
                                      ("reasoning_output_tokens", "output_tokens")):
                    if values[subset] is not None and values[total] is not None and values[subset] > values[total]:
                        raise ValueError("Invalid token subset")
                if all(values[f] is not None for f in fields[:3]) and values["input_tokens"] + values["output_tokens"] != values["total_tokens"]:
                    raise ValueError("Inconsistent token totals")
                key = (day.isoformat(), stage, model)
                group = groups.setdefault(key, {
                    "date_ct": key[0], "stage": stage, "model": model,
                    "logged_requests": 0, "completed_requests": 0,
                    "failed_requests": 0, "other_status_requests": 0,
                    "completed_without_output_text": 0,
                    "tokens": {f: {"known_sum": 0, "missing_records": 0} for f in fields},
                })
                group["logged_requests"] += 1
                status = row.get("status")
                if status == "completed":
                    group["completed_requests"] += 1
                    if row.get("output_text_present") is not True:
                        group["completed_without_output_text"] += 1
                elif status in ("request_failed", "failed"):
                    group["failed_requests"] += 1
                else:
                    group["other_status_requests"] += 1
                for field, value in values.items():
                    group["tokens"][field]["known_sum"] += value if value is not None else 0
                    group["tokens"][field]["missing_records"] += int(value is None)
            except (ValueError, TypeError, KeyError, OverflowError):
                result["invalid_records"] += 1
    result["groups"] = [groups[key] for key in sorted(groups)]
    if not groups:
        result["status"] = "no_valid_records_in_window"
    return result


def usage_payload(base):
    try:
        summary = usage_summary(base)
    except Exception:
        # Reporting failure must neither block cameras nor leave a stale success file.
        summary = {"schema_version": 1, "status": "unavailable",
                   "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                   "billing_status": "unpriced_token_usage_not_actual_spend", "groups": []}
    return json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload(base):
    frames = base / 'frames'
    raw = {name: (frames / name).read_bytes() for name in METADATA}
    docs = {name: json.loads(value.decode('utf-8-sig')) for name, value in raw.items()}
    status = docs['status.json']
    now = datetime.now(timezone.utc)
    captured = timestamp(status['capture_time_ct'])
    if not -timedelta(minutes=2) <= now - captured <= timedelta(minutes=60):
        raise ValueError('Capture stale or in the future')
    for doc in docs.values():
        validate_private(doc)
        if doc.get('capture_time_ct') != status['capture_time_ct']:
            raise ValueError('Capture metadata mismatch')
    for camera in CAMERAS:
        info = status.get('cameras', {}).get(camera, {})
        name = camera + '.jpg'
        raw[name] = None
        if info.get('ok') is True:
            age = now - timestamp(info['timestamp_ct'])
            if not -timedelta(minutes=2) <= age <= timedelta(minutes=60):
                raise ValueError('Camera timestamp stale or in the future')
            content = (frames / name).read_bytes()
            if not content.startswith(b'\xff\xd8') or not content.endswith(b'\xff\xd9'):
                raise ValueError('Invalid JPEG')
            raw[name] = content
    raw["api_usage_summary.json"] = usage_payload(base)
    return raw, captured

def publish(base=BASE, attempts=3, before_push=None):
    repo = base / 'jubilee-camera-feed'
    files, captured = payload(base)
    with tempfile.TemporaryDirectory(prefix='jubilee-publish-') as temp:
        env = os.environ.copy()
        env['GIT_INDEX_FILE'] = str(Path(temp) / 'index')
        for attempt in range(attempts):
            git(repo, 'fetch', '--quiet', 'origin', 'refs/heads/main')
            parent = git(repo, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
            prior = git(repo, 'show', parent + ':status.json', check=False)
            if prior.returncode == 0:
                prior_time = json.loads(prior.stdout.decode('utf-8-sig')).get('capture_time_ct')
                if prior_time and timestamp(prior_time) > captured:
                    raise ValueError('Remote camera snapshot is newer')
            git(repo, 'read-tree', parent, env=env)
            for name, content in files.items():
                if content is None:
                    git(repo, 'update-index', '--force-remove', '--', name, env=env)
                else:
                    blob = git(repo, 'hash-object', '-w', '--stdin', data=content).stdout.decode().strip()
                    git(repo, 'update-index', '--add', '--cacheinfo', '100644', blob, name, env=env)
            tree = git(repo, 'write-tree', env=env).stdout.decode().strip()
            old_tree = git(repo, 'rev-parse', parent + '^{tree}').stdout.decode().strip()
            if tree == old_tree:
                print('NO GITHUB CHANGES')
                return parent
            commit = git(repo, 'commit-tree', tree, '-p', parent, '-m',
                         'Latest Jubilee camera burst - ' + captured.isoformat()).stdout.decode().strip()
            if before_push:
                before_push(attempt)
            pushed = git(repo, 'push', '--quiet', 'origin', commit + ':refs/heads/main', check=False)
            if pushed.returncode == 0:
                print('GITHUB APPEND-ONLY PUBLISH SUCCESS: ' + commit)
                return commit
            if attempt + 1 < attempts:
                time.sleep(1)
    raise RuntimeError('Publication failed after bounded retries; no force push attempted')

if __name__ == '__main__':
    try:
        publish()
    except Exception as exc:
        print('Publication refused: ' + str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Publication failed: ' + type(exc).__name__)
        raise SystemExit(1)


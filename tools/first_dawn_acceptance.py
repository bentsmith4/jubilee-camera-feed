"""One date, one event-armed, read-only production audit, one issue receipt.

No acquisition, publication repair, workflow rerun, or model mutation is allowed.
The hard-coded window is Astral 3.2 civil dawn for the deployed observer
(30.6035, -87.9036, elevation 0); independently reproduced in regression tests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model_data'))
REPO = 'bentsmith4/jubilee-camera-feed'
DEPLOYED = 'd56f884596ab8709dfd78d57e5317784c2ea25d4'
RECONCILER = '4da28a059e29055390cac15602c368646764030e'
MARKER = '<!-- jubilee-first-full-dawn-20260929-v1 -->'
ISSUE = 26
PREFIX = 'Latest Jubilee camera burst - '
CAMERAS = ('montrose_pier_boat', 'montrose_pier_bird', 'montrose_shoreline',
           'pcl_e2_back_deck', 'pcl_e2_bay_mouth', 'pcl_e3_bay_mouth')
METADATA = ('status.json', 'burst_status.json', 'vision.json')
SNAPSHOT = 'model_data/current_state_snapshot.json'
FORECAST = 'model_data/current_forecast.json'
DAWN = datetime.fromisoformat('2026-09-29T06:19:45.673391-05:00')
START, END = DAWN - timedelta(hours=2), DAWN + timedelta(hours=2)
DEADLINE = END + timedelta(minutes=45)
ALLOWLIST = set(METADATA) | {c + '.jpg' for c in CAMERAS} | {'api_usage_summary.json'}
SHA = re.compile(r'^[0-9a-f]{40}$')


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('offset-aware timestamp required')
    return result


def git(root, *args, check=True):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=120)
    if check and result.returncode:
        raise ValueError('Git evidence unavailable: ' + args[0])
    return result


def blob(root, ref, name):
    if not SHA.fullmatch(ref):
        raise ValueError('expected pinned commit SHA')
    return git(root, 'show', ref + ':' + name).stdout


def doc(root, ref, name):
    return json.loads(blob(root, ref, name))


def ancestor(root, older, newer):
    return bool(SHA.fullmatch(older) and SHA.fullmatch(newer) and
                git(root, 'merge-base', '--is-ancestor', older, newer, check=False).returncode == 0)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self):
        self.token = os.environ['GH_TOKEN']
        self.opener = urllib.request.build_opener(NoRedirect)
        self.completed_runs = {}

    def request(self, path, body=None, raw=False):
        url = 'https://api.github.com/repos/' + REPO + '/' + path
        headers = {'Authorization': 'Bearer ' + self.token,
                   'Accept': 'application/vnd.github+json',
                   'Content-Type': 'application/json',
                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'jubilee-dawn-acceptance'}
        payload = None if body is None else json.dumps(body).encode()
        try:
            with self.opener.open(urllib.request.Request(url, data=payload, headers=headers), timeout=60) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and raw and body is None:
                # Signed Actions log redirects receive NO GitHub credentials.
                location = exc.headers['Location']
                if urllib.parse.urlsplit(location).scheme != 'https':
                    raise ValueError('insecure log redirect') from None
                with urllib.request.urlopen(location, timeout=60) as response:
                    content = response.read()
            else:
                raise ValueError('GitHub API status ' + str(exc.code) + ' for ' + path.split('?')[0]) from None
        return content.decode('utf-8-sig') if raw else json.loads(content)

    def pages(self, path, key=None):
        rows = []
        for page in range(1, 21):
            payload = self.request(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            batch = payload[key] if key else payload
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ValueError('GitHub pagination bound reached; evidence incomplete')

    def receipts(self):
        return [r for r in self.pages(f'issues/{ISSUE}/comments')
                if MARKER in r.get('body', '') and r.get('user', {}).get('login') == 'github-actions[bot]']


def canonical_commits(root, ref):
    """Read first-parent publication order, never infer order from wall-clock sort."""
    if not ancestor(root, DEPLOYED, ref) or not ancestor(root, RECONCILER, ref):
        raise ValueError('required reviewed deployment/reconciliation ancestry missing')
    rows = []
    output = git(root, 'log', '--first-parent', '--reverse', '--format=%H%x09%cI%x09%s',
                 '--grep=^' + PREFIX, DEPLOYED + '..' + ref).stdout.decode()
    for line in output.splitlines():
        sha, published, subject = line.split('\t', 2)
        captured = stamp(subject[len(PREFIX):])
        rows.append(dict(sha=sha, published=published, capture_time_ct=captured.isoformat()))
    return rows


def eligible(root, ref):
    candidates = [r for r in canonical_commits(root, ref)
                  if START <= stamp(r['capture_time_ct']) <= END]
    return bool(candidates and candidates[0]['sha'] == ref)


def activity_reasons(vision, now):
    """Explicit predicates from deployed capture_service.strong_activity_evidence."""
    age = now - stamp(vision['capture_time_ct'])
    if not -timedelta(minutes=5) <= age <= timedelta(minutes=60):
        return []
    reasons = []
    for field in ('overall_visual_jubilee_signal', 'montrose_visual_signal', 'point_clear_visual_signal'):
        value = vision.get('cross_camera', {}).get(field)
        if value in ('moderate', 'strong'):
            reasons.append('cross_camera.' + field + '=' + value)
    for camera, row in vision.get('cameras', {}).items():
        if row.get('status') != 'ok':
            continue
        for field in ('temporal_jubilee_signal', 'overall_jubilee_visual_signal'):
            if row.get(field) in ('moderate', 'strong'):
                reasons.append(camera + '.' + field + '=' + row[field])
        for field in ('flashlight_activity', 'clustered_search_behavior', 'people_collecting_seafood'):
            if row.get(field) == 'clear':
                reasons.append(camera + '.' + field + '=clear')
        score = row.get('human_sensor_score')
        if (type(score) in (int, float) and score >= .5 and
                row.get('human_sensor_detectability') not in ('poor', 'unknown') and
                row.get('motion_pattern') == 'searching'):
            reasons.append(camera + '.human_sensor_score=' + str(score) + '; searching')
    return reasons


def validate_camera(root, row):
    from PIL import Image
    documents = {name: doc(root, row['sha'], name) for name in METADATA}
    s, b, v = (documents[name] for name in METADATA)
    errors = []

    def require(ok, reason):
        if not ok:
            errors.append(reason)

    captured = stamp(row['capture_time_ct'])
    published = stamp(row['published'])
    require(captured <= published, 'capture timestamp is after publication')
    ids = [d.get('capture_id') for d in documents.values()]
    require(not any(ids) or (all(ids) and len(set(ids)) == 1), 'capture_id mismatch')
    for name, data in documents.items():
        require(data.get('capture_time_ct') == row['capture_time_ct'], name + ': capture identity mismatch')
        require(set(data.get('cameras', {})) == set(CAMERAS), name + ': expected six-camera set mismatch')
        require(stamp(data['dawn_ct']).date() == captured.date(), name + ': wrong dawn date')
        if captured.date() == DAWN.date():
            require(stamp(data['dawn_ct']) == DAWN, name + ': configured dawn mismatch')
    for data in (s, v):
        require(stamp(data['window_start_ct']) == stamp(data['dawn_ct']) - timedelta(hours=2) and
                stamp(data['window_end_ct']) == stamp(data['dawn_ct']) + timedelta(hours=2),
                'configured dawn window mismatch')
    require(s.get('burst_count') == b.get('burst_count') == 3, 'top-level burst count mismatch')
    require(v.get('analysis_type') == 'three_frame_temporal_burst', 'vision analysis type mismatch')
    for camera in CAMERAS:
        try:
            cs, cb, cv = (d['cameras'][camera] for d in (s, b, v))
            require(cs.get('ok') is True and cb.get('ok') is True and cv.get('status') == 'ok',
                    camera + ': capture/burst/vision not all successful')
            shots = cb['shots']
            require(len(shots) == 3 and [x['shot'] for x in shots] == [1, 2, 3], camera + ': shot order/count')
            times = [stamp(x['timestamp_ct']) for x in shots]
            require(len(times) == 3 and all(5 <= (y-x).total_seconds() <= 30 for x, y in zip(times, times[1:])),
                    camera + ': shot timing outside existing 5–30 second integrity contract')
            require(captured <= times[0] < times[-1] <= published, camera + ': shot outside capture/publication bounds')
            require(cv.get('camera_id') == camera and cv.get('burst_frame_count') == cs.get('burst_count') == 3,
                    camera + ': vision identity/frame count')
            require(cv.get('burst_shots') == shots, camera + ': vision does not refer to these exact shots')
            require(cs['timestamp_ct'] == shots[-1]['timestamp_ct'], camera + ': latest is not third shot')
            require(all(x['file'] == f'{camera}_{i}.jpg' and x['bytes'] > 0 for i, x in enumerate(shots, 1)),
                    camera + ': invalid shot file/byte identity')
            pixels = blob(root, row['sha'], camera + '.jpg')
            require(len(pixels) == cs['bytes'] == shots[-1]['bytes'], camera + ': latest image byte mismatch')
            with Image.open(io.BytesIO(pixels)) as image:
                require(image.format == 'JPEG', camera + ': invalid JPEG')
                image.load()
        except (KeyError, TypeError, ValueError, IndexError, OSError) as exc:
            errors.append(camera + ': invalid/missing evidence (' + type(exc).__name__ + ')')
    parents = git(root, 'show', '-s', '--format=%P', row['sha']).stdout.decode().split()
    require(len(parents) == 1, 'camera publication must have one parent')
    changed = set(git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', row['sha']).stdout.decode().splitlines())
    require(set(METADATA) <= changed <= ALLOWLIST, 'camera publication changed nonallowlisted/missing metadata paths')
    require(ancestor(root, DEPLOYED, row['sha']) and ancestor(root, RECONCILER, row['sha']), 'publication ancestry failed')
    row['input_hashes'] = {name: digest(blob(root, row['sha'], name)) for name in METADATA}
    row['vision'] = v
    row['errors'] = errors
    return row


def cadence(rows):
    errors, slots, intervals = [], {}, []
    previous = None
    for row in rows:
        t = stamp(row['capture_time_ct'])
        in_window = START <= t <= END
        if previous:
            pt = stamp(previous['capture_time_ct'])
            seconds = (t-pt).total_seconds()
            interval = dict(previous=pt.isoformat(), current=t.isoformat(), seconds=seconds)
            intervals.append(interval)
            if seconds < 900:
                errors.append(f'GLOBAL_SPACING: {pt.isoformat()} -> {t.isoformat()} = {seconds:.6f}s < 900s')
            # Publication precedes coordinator success. This is a necessary lower
            # bound on its completion-to-start floor, not a local heartbeat claim.
            completion_gap = (t-stamp(previous['published'])).total_seconds()
            interval['seconds_after_prior_publication'] = completion_gap
            if completion_gap < 900:
                errors.append(f'COMPLETION_FLOOR: published {previous["published"]} -> {t.isoformat()} = {completion_gap:.6f}s < 900s')
        if in_window:
            index = int((t-START).total_seconds() // 1200)
            row['slot'] = index
            row['slot_delay_seconds'] = (t-(START + timedelta(minutes=20*index))).total_seconds()
            row['kind'] = 'regular'
            if index in slots:
                reasons = activity_reasons(previous.get('vision', {}), t) if previous else []
                if t >= DAWN or not reasons:
                    errors.append('UNJUSTIFIED_ADAPTIVE: ' + t.isoformat() + ' repeats slot ' + str(index))
                row['kind'] = 'adaptive'
                row['activity_evidence'] = reasons
                row['activity_evidence_commit'] = previous['sha'] if previous else None
            else:
                slots[index] = row['sha']
        previous = row
    # The deployed coordinator uses floor(elapsed/20m) while now <= end.
    # There are twelve positive-duration slots; index 12 exists only at the
    # exact endpoint microsecond, and is audited if present but not fabricated.
    missing = sorted(set(range(12)) - slots.keys())
    if missing:
        errors.append('MISSING_REGULAR_SLOTS: ' + ', '.join(
            f'{i} ({(START+timedelta(minutes=20*i)).isoformat()})' for i in missing))
    return errors, intervals


def log_objects(log):
    """Extract machine JSON from timestamp-prefixed Actions logs, not echoed code."""
    clean = re.sub(r'(?m)^\d{4}-\d\d-\d\dT\S+Z\s?', '', log)
    decoder, values = json.JSONDecoder(), []
    for match in re.finditer(r'\{', clean):
        try:
            value, _ = decoder.raw_decode(clean[match.start():])
            if isinstance(value, dict):
                values.append(value)
        except ValueError:
            pass
    return values


def workflow_evidence(api):
    result = []
    since = (START-timedelta(hours=2)).astimezone(timezone.utc).isoformat()
    for workflow in ('observation_logging.yml', 'current_state_freshness.yml'):
        query = urllib.parse.urlencode({'branch': 'main', 'created': '>=' + since})
        runs = api.pages(f'actions/workflows/{workflow}/runs?{query}', 'workflow_runs')
        for run in runs:
            if stamp(run['created_at']) > DEADLINE or run['event'] == 'pull_request':
                continue
            cache_key = (run['id'], run.get('run_attempt', 1))
            if cache_key in api.completed_runs:
                result.append(api.completed_runs[cache_key])
                continue
            summary = {k: run.get(k) for k in ('id', 'head_sha', 'status', 'conclusion', 'html_url', 'created_at')}
            summary['workflow'] = workflow
            summary['jobs'] = []
            for job in api.pages(f'actions/runs/{run["id"]}/jobs?filter=latest', 'jobs'):
                if job['name'] not in ('record', 'reconcile', 'current-state-status'):
                    continue
                entry = {k: job.get(k) for k in ('id', 'name', 'conclusion', 'started_at', 'completed_at')}
                entry['failed_steps'] = [s['name'] for s in job.get('steps', [])
                                         if s.get('conclusion') in ('failure', 'timed_out')]
                entry['objects'] = []
                if job['status'] == 'completed' and job['conclusion'] == 'success':
                    values = log_objects(api.request(f'actions/jobs/{job["id"]}/logs', raw=True))
                    entry['objects'] = [v for v in values if
                        ('record' in v and 'status' in v) or
                        ('evidence_commit' in v and 'status' in v) or
                        ('snapshot_sha256' in v and 'sources' in v and 'status' in v)]
                summary['jobs'].append(entry)
            if run['status'] == 'completed':
                api.completed_runs[cache_key] = summary
            result.append(summary)
    return result


def observation_check(root, ref, row, runs):
    name = 'model_data/observation_records/' + digest(row['capture_time_ct'].encode())[:24] + '.json'
    record = doc(root, ref, name)
    if (record.get('input_hashes') != row['input_hashes'] or
            record.get('generated_from_capture_time_ct') != row['capture_time_ct'] or
            record.get('production_action') != 'NO_CHANGE' or record.get('clean_training_negative_count') != 0):
        raise ValueError('observation record identity/hash/guardrail mismatch: ' + name)
    cameras = [c for cell in record['cells'] for c in cell['camera_rows']]
    if len(cameras) != 6 or {c['camera_id'] for c in cameras} != set(CAMERAS) or any(
            c.get('capture_ok') is not True or c.get('integrity_issues') for c in cameras):
        raise ValueError('observation record failed six-camera integrity: ' + name)
    for run in runs:
        if run['workflow'] != 'observation_logging.yml' or run['conclusion'] != 'success':
            continue
        for job in run['jobs']:
            for result in job['objects']:
                commit = result.get('commit', '')
                if (job['name'] == 'record' and result.get('record') == name and
                        result.get('status') in ('published', 'already_recorded') and
                        ancestor(root, row['sha'], commit) and ancestor(root, commit, ref) and
                        doc(root, commit, name) == record):
                    return dict(record=name, run_id=run['id'], commit=commit)
    raise ValueError('no successful unattended observation run with matching durable receipt: ' + name)


def reconciliation_check(root, ref, row, runs):
    import bind_current_forecast as binding
    for run in runs:
        if run['workflow'] != 'current_state_freshness.yml':
            continue
        jobs = {j['name']: j for j in run['jobs']}
        if any(jobs.get(n, {}).get('conclusion') != 'success' for n in ('reconcile', 'current-state-status')):
            continue
        for receipt in jobs['reconcile']['objects']:
            if receipt.get('status') not in ('published', 'already_current'):
                continue
            commit = receipt.get('commit', receipt.get('evidence_commit', ''))
            if not ancestor(root, row['sha'], commit) or not ancestor(root, commit, ref):
                continue
            raw = blob(root, commit, SNAPSHOT)
            snapshot = json.loads(raw)
            provenance = snapshot['reconciliation']['source_provenance']
            if any(provenance.get(n, {}).get('sha256') != h for n, h in row['input_hashes'].items()):
                continue
            binding.check(raw, doc(root, commit, FORECAST))
            source = snapshot['reconciliation']['input_commit_sha']
            if not ancestor(root, row['sha'], source) or not ancestor(root, source, commit):
                raise ValueError('reconciled snapshot input ancestry invalid: ' + commit)
            if any(digest(blob(root, source, n)) != p['sha256'] for n, p in provenance.items()):
                raise ValueError('reconciled provenance not from declared committed input: ' + commit)
            lag = (stamp(snapshot['snapshot_time_ct'])-stamp(row['published'])).total_seconds()/60
            if not 0 <= lag <= 30:
                raise ValueError(f'reconciliation lag {lag:.3f} minutes for {row["capture_time_ct"]}: {commit}')
            reports = [o for o in jobs['current-state-status']['objects']
                       if o.get('snapshot_sha256') == digest(raw) and o.get('status') == 'CURRENT']
            if reports:
                return dict(commit=commit, input_commit=source, run_id=run['id'], lag_minutes=round(lag, 3),
                            snapshot_sha256=digest(raw), status='CURRENT')
    raise ValueError('no successful reconciliation + CURRENT status bound to this exact camera evidence')


def audit(root, ref, runs, now):
    errors, pending = [], []
    all_rows = canonical_commits(root, ref)
    dawn_rows = [r for r in all_rows if START <= stamp(r['capture_time_ct']) <= END]
    before = [r for r in all_rows if stamp(r['capture_time_ct']) < START]
    after = [r for r in all_rows if stamp(r['capture_time_ct']) > END]
    selected = before[-1:] + dawn_rows + after[:1]
    if not before:
        errors.append('missing preceding baseline evidence for dawn handoff')
    if not after:
        pending.append('first post-window canonical capture is not published')
    for row in selected:
        try:
            validate_camera(root, row)
            errors.extend(row['capture_time_ct'] + ' ' + e for e in row['errors'])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(row['capture_time_ct'] + ' CAMERA_EVIDENCE: ' + str(exc))
            row.setdefault('vision', {})
    try:
        cadence_errors, intervals = cadence(selected)
        errors.extend(cadence_errors)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append('CADENCE_EVIDENCE: ' + str(exc))
        intervals = []
    for row in dawn_rows:
        for name, check in (('observation', observation_check), ('reconciliation', reconciliation_check)):
            try:
                row[name] = check(root, ref, row, runs)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                pending.append(row['capture_time_ct'] + ' ' + name.upper() + ': ' + str(exc))
    dawn_shas = {r['sha'] for r in dawn_rows}
    for run in runs:
        during_window = bool(dawn_rows and run.get('created_at') and
                             stamp(dawn_rows[0]['published']) <= stamp(run['created_at']) <=
                             stamp(dawn_rows[-1]['published']) + timedelta(minutes=30))
        if (run['head_sha'] in dawn_shas or during_window) and run['conclusion'] in ('failure', 'timed_out', 'action_required'):
            steps = [step for job in run['jobs'] for step in job.get('failed_steps', [])]
            errors.append(f'WORKFLOW_FAILURE: run {run["id"]} {run["workflow"]} {run["conclusion"]}; '
                          f'head {run["head_sha"]}; failed steps {steps}')
    # Re-run the existing full admissibility/freshness and binding contracts on
    # one pinned final tree, never on mutable working files or failed artifacts.
    import bind_current_forecast as binding
    import check_current_state_freshness as freshness
    with tempfile.TemporaryDirectory(prefix='dawn-acceptance-') as temp:
        checkout = Path(temp)/'evidence'
        git(root, 'worktree', 'add', '--quiet', '--detach', str(checkout), ref)
        try:
            binding.check((checkout/SNAPSHOT).read_bytes(), json.loads((checkout/FORECAST).read_bytes()))
            guard = freshness.inspect(checkout, now)
            if guard['status'] != 'CURRENT':
                pending.append('FINAL_FRESHNESS: ' + json.dumps(guard, sort_keys=True))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            guard = dict(status='ERROR', reason=str(exc), checked_commit=ref)
            errors.append('FINAL_BINDING_OR_FRESHNESS: ' + ref + ' ' + str(exc))
        finally:
            git(root, 'worktree', 'remove', '--force', str(checkout))
    if now < END:
        pending.append('full dawn window has not ended')
    for row in selected:
        row.pop('vision', None)
    return dict(status='FAIL' if errors else ('PENDING' if pending else 'PASS'),
                target_date='2026-09-29', window_start_ct=START.isoformat(), dawn_ct=DAWN.isoformat(),
                window_end_ct=END.isoformat(), deadline_ct=DEADLINE.isoformat(),
                checked_at_utc=now.astimezone(timezone.utc).isoformat(), checked_commit=ref,
                first_dawn_commit=dawn_rows[0]['sha'] if dawn_rows else None,
                errors=errors, pending=pending, captures=selected, intervals=intervals,
                freshness=guard, workflow_runs=runs,
                scope='Published canonical cycles only; no claim about unpublished attempts, local coordinator logs, private archives or R2. No biological negative inferred.')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def observe(root, api, out):
    # Bounded one-time wait, not a recurring schedule. The runner exits forever
    # after this date's receipt. Leave a FAIL fallback before the first wait.
    save(out, dict(status='FAIL', errors=['Acceptance interrupted before complete evidence was collected.'], captures=[]))
    while datetime.now(timezone.utc) < END + timedelta(minutes=10):
        time.sleep(30)
    while True:
        now = datetime.now(timezone.utc)
        try:
            git(root, 'fetch', '--quiet', 'origin', 'refs/heads/main')
            ref = git(root, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
            result = audit(root, ref, workflow_evidence(api), now)
        except Exception as exc:
            result = dict(status='PENDING', errors=[], pending=['Evidence collection failed: ' + str(exc)], captures=[])
        if now >= DEADLINE or not result.get('pending'):
            if result.get('pending'):
                result['status'] = 'FAIL'
                result['errors'].extend('INCOMPLETE_AT_DEADLINE: ' + e for e in result['pending'])
            save(out, result)
            return
        # Do not leave a premature PASS or a PENDING fallback if the job stops.
        checkpoint = dict(result, status='FAIL')
        checkpoint['errors'] = result['errors'] + ['Acceptance interrupted before downstream settlement.']
        save(out, checkpoint)
        time.sleep(60)


def markdown(result):
    lines = [MARKER, '@bentsmith4', '', '# First complete dawn acceptance: ' + result['status'], '',
             f'Target: September 29, 2026, **{START.isoformat()} – {END.isoformat()}**.',
             'Deployment: issue #26, September 28 at 10:55–10:58 CDT; reviewed commit `' + DEPLOYED + '`.',
             'Evidence commit: `' + result.get('checked_commit', 'UNAVAILABLE') + '`.', '',
             '| Capture (CDT) | Commit | Slot / kind | Slot delay (s) | Observation run | Reconciliation run |',
             '|---|---|---|---:|---|---|']
    for row in result.get('captures', []):
        lines.append('| ' + ' | '.join([row['capture_time_ct'], '`'+row['sha'][:12]+'`',
                     str(row.get('slot', 'handoff')) + ' / ' + row.get('kind', 'baseline'),
                     str(round(row['slot_delay_seconds'], 3)) if 'slot_delay_seconds' in row else '—',
                     str(row.get('observation', {}).get('run_id', '—')),
                     str(row.get('reconciliation', {}).get('run_id', '—'))]) + ' |')
    if result['status'] == 'PASS':
        count = sum('slot' in r for r in result.get('captures', []))
        lines += ['', f'**Verified:** {count} dawn captures; six expected cameras and 18 ordered shots per capture; '
                  'coherent vision and latest JPEGs; matching successful observation and reconciliation receipts for every dawn capture; '
                  'reviewed publication ancestry; final forecast binding and CURRENT freshness.',
                  'Final bound snapshot SHA-256: `' + result.get('freshness', {}).get('snapshot_sha256', 'UNAVAILABLE') + '`.']
    lines += ['', '| Previous capture → next capture | Seconds between starts | Seconds after prior publication |',
              '|---|---:|---:|']
    for row in result.get('intervals', []):
        lines.append(f'| {row["previous"]} → {row["current"]} | {row["seconds"]:.6f} | {row["seconds_after_prior_publication"]:.6f} |')
    lines += ['', '20-minute cadence is evaluated against the deployed fixed slots; actual delays are shown above. '
              'Repeated-slot captures require explicit fresh, stronger pre-dawn activity evidence. '
              'Both start-to-start and publication-to-next-start 15-minute lower bounds are checked.', '']
    for row in result.get('captures', []):
        if row.get('kind') == 'adaptive':
            lines.append('- Adaptive ' + row['capture_time_ct'] + ': ' + '; '.join(row.get('activity_evidence', [])) +
                         '; evidence commit `' + str(row.get('activity_evidence_commit')) + '`.')
    lines += ['## Failures / missing evidence', '']
    lines += ['- ' + e for e in result.get('errors', [])] or ['- None.']
    canceled = [r['id'] for r in result.get('workflow_runs', []) if r['conclusion'] == 'cancelled']
    lines += ['', 'Cancelled runs inspected: ' + (', '.join(map(str, canceled)) or 'none') +
              '. Cancellation alone is not acceptance failure; each dawn capture still needs matching successful observation and reconciliation receipts.',
              '', result.get('scope', 'No completed evidence audit is claimed.'),
              '', 'Detailed hashes, source freshness and job evidence are in the workflow artifact. '
              'This one-time acceptance is finished; no further receipt will be posted.']
    run = os.environ.get('GITHUB_RUN_ID')
    if run:
        lines.append(f'\n[Acceptance workflow and JSON artifact](https://github.com/{REPO}/actions/runs/{run})')
    body = '\n'.join(lines)
    if len(body) > 60000:
        body = body[:58000] + '\n\nReport truncated; see complete JSON artifact in the acceptance workflow.\n' + MARKER
    return body


def post_report(api, path):
    if api.receipts():
        print('Final receipt already exists; no duplicate notification.')
        return
    if not path.exists():
        save(path, dict(status='FAIL', errors=['Workflow failed before an evidence report was produced.'], captures=[]))
    result = json.loads(path.read_text())
    if result.get('status') not in ('PASS', 'FAIL'):
        result['status'] = 'FAIL'
        result.setdefault('errors', []).append('Acceptance did not reach a terminal verdict.')
        save(path, result)
    body = markdown(result)
    # No blind retry of this POST: after an ambiguous transport failure, a rerun
    # re-reads the durable marker before attempting another notification.
    receipt = api.request(f'issues/{ISSUE}/comments', {'body': body})
    if MARKER not in receipt.get('body', ''):
        raise ValueError('final receipt readback did not contain acceptance marker')
    print('Final receipt: ' + receipt['html_url'])
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('gate', 'observe', 'report'))
    parser.add_argument('--out', type=Path, default=Path('first-dawn.json'))
    args = parser.parse_args()
    api = GitHub()
    if args.action == 'gate':
        ref = os.environ['GITHUB_SHA']
        armed = not api.receipts() and eligible(ROOT, ref)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('armed=' + str(armed).lower() + '\n')
        print('First complete dawn acceptance armed=' + str(armed).lower())
    elif args.action == 'observe':
        observe(ROOT, api, args.out)
    else:
        post_report(api, args.out)


if __name__ == '__main__':
    main()

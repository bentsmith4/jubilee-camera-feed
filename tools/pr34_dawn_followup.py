"""One terminal dawn receipt -> one PR34 handoff or blocker; no desktop writes.

workflow_run is only a wake-up for GITHUB_TOKEN-produced comments. Nothing is
prepared before the exact, authenticated September 29 acceptance is terminal.
The receipt marker plus workflow concurrency makes reruns and later wakes no-ops.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from string import Template

import first_dawn_acceptance as dawn

ROOT = Path(__file__).resolve().parents[1]
MERGE = '6c4d479afec15a840decb56b16fc94f74ba4006e'
PR_HEAD = '52753abecbb210a20ee745a4c21c6f34575b1c7f'
BASELINE = '47f1f6d69408903ed7e6965dcbaf06033330c84e'
MARKER = '<!-- jubilee-pr34-post-dawn-20260929-v1 -->'
FILES = ('desktop_runtime/burst_capture.py', 'desktop_runtime/capture_diagnostics.py')
WORKFLOW = '.github/workflows/first_dawn_acceptance.yml'
CHECKS = ('unittest', 'windows-preflight', 'offline-validation')
EXPECTED = {
    FILES[0]: '519bca8eeee2a0b16934df1e5dce9ffdfed15e8c8e74a6402d14de8dd24efc1c',
    FILES[1]: '4ae0a72b88be276d2a3772b9133ecdd45de4b0c47a35b4726a7586e756bdd062',
}


def trusted(comment, marker):
    return (comment.get('user', {}).get('login') == 'github-actions[bot]' and
            comment.get('body', '').splitlines()[:1] == [marker])


def terminal(comments):
    candidates = [c for c in comments if trusted(c, dawn.MARKER)]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise ValueError('Multiple September 29 acceptance receipts; reconcile the ambiguity first.')
    comment = candidates[0]
    matches = re.findall(r'^# First complete dawn acceptance: (PASS|FAIL)$', comment['body'], re.M)
    if len(matches) != 1 or 'Target: September 29, 2026,' not in comment['body']:
        raise ValueError('Acceptance marker exists without an unambiguous target-date terminal verdict.')
    verdict = matches[0]
    created = dawn.stamp(comment['created_at'])
    if created < dawn.START or (verdict == 'PASS' and created < dawn.END):
        raise ValueError('Acceptance timestamp precedes its allowed terminal window.')
    return comment, verdict


def validate_origin(api, comment, event):
    runs = re.findall(r'https://github\.com/' + re.escape(dawn.REPO) +
                      r'/actions/runs/(\d+)\)', comment['body'])
    if len(runs) != 1:
        raise ValueError('Acceptance receipt does not identify exactly one producer run.')
    run = api.request('actions/runs/' + runs[0])
    if not (run.get('path') == WORKFLOW and run.get('head_branch') == 'main' and
            run.get('event') == 'push' and run.get('repository', {}).get('full_name') == dawn.REPO and
            run.get('head_repository', {}).get('full_name') == dawn.REPO):
        raise ValueError('Receipt run is not the canonical main-branch dawn acceptance producer.')
    # A comment event can arrive before the producer finishes uploading evidence.
    # Wait for its workflow_run completion rather than prepare under active test.
    if run.get('status') != 'completed':
        return False
    if event.get('workflow_run') and event['workflow_run']['id'] != run['id']:
        return False
    if event.get('comment') and event['comment']['id'] != comment['id']:
        return False
    if ('# First complete dawn acceptance: PASS\n' in comment['body'] and
            run.get('conclusion') != 'success'):
        raise ValueError('PASS comment exists but its producer did not finish successfully; review required.')
    jobs = api.pages(f'actions/runs/{run["id"]}/jobs', 'jobs')
    steps = [s for j in jobs for s in j.get('steps', [])
             if s.get('name') == 'Post exactly one final acceptance receipt to issue 26']
    if len(steps) != 1 or steps[0].get('conclusion') != 'success':
        raise ValueError('Producer run lacks a successful terminal-comment publication step.')
    return True


def check_pr(api):
    pr = api.request('pulls/34')
    if not (pr.get('merged') is True and pr.get('state') == 'closed' and
            pr.get('merge_commit_sha') == MERGE and pr['head']['sha'] == PR_HEAD and
            pr['base']['ref'] == 'main' and pr['base']['repo']['full_name'] == dawn.REPO and
            pr['head']['repo']['full_name'] == dawn.REPO):
        raise ValueError('PR #34 identity, merge, or branch evidence changed; review required.')
    checks = api.pages(f'commits/{PR_HEAD}/check-runs', 'check_runs')
    verified = []
    for name in CHECKS:
        matches = [c for c in checks if c['name'] == name and c.get('app', {}).get('slug') == 'github-actions']
        if not matches:
            raise ValueError('Missing PR34 check: ' + name)
        latest = max(matches, key=lambda c: c['id'])
        if latest.get('status') != 'completed' or latest.get('conclusion') != 'success':
            raise ValueError('PR34 check is not green: ' + name)
        verified.append(latest)
    return pr, verified


def source_evidence(root, ref, pr):
    for required in (MERGE, dawn.DEPLOYED, dawn.RECONCILER,
                     '257482cfe2c0e9f8890417bdb38e403b73bd3b1d',
                     '1edd9e97ff7fff13216fee6237e482690ce9dae0'):
        if not dawn.ancestor(root, required, ref):
            raise ValueError('Current main lacks required ancestry: ' + required)
    rows = []
    for name in FILES:
        raw = dawn.blob(root, ref, name)
        if dawn.digest(raw) != EXPECTED[name] or raw != dawn.blob(root, MERGE, name):
            raise ValueError('Runtime source changed since reviewed PR34: ' + name)
        compile(raw, name, 'exec')  # syntax only; never import/acquire cameras
        rows.append(dict(path=name, name=Path(name).name, sha256=dawn.digest(raw),
                         blob=dawn.git(root, 'rev-parse', ref + ':' + name).stdout.decode().strip(),
                         previous_sha256=dawn.digest(dawn.blob(root, pr['base']['sha'], name))))
    service = 'desktop_runtime/capture_service.py'
    if dawn.blob(root, ref, service) != dawn.blob(root, dawn.DEPLOYED, service):
        raise ValueError('Coordinator source differs from the accepted deployment; separate review required.')
    return rows


def observed_diagnostics(root, ref):
    docs = {name: dawn.doc(root, ref, name) for name in ('status.json', 'burst_status.json')}
    return '; '.join(name + ': capture ' + str(doc.get('capture_time_ct')) + ', ' +
                     str(sum('capture_attempts' in c for c in doc.get('cameras', {}).values())) +
                     '/' + str(len(doc.get('cameras', {}))) + ' camera rows have capture_attempts'
                     for name, doc in docs.items())


def prepare(root, api, receipt):
    pr, checks = check_pr(api)
    dawn.git(root, 'fetch', '--quiet', 'origin', 'refs/heads/main')
    ref = dawn.git(root, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
    rows = source_evidence(root, ref, pr)
    # Pin exact source bytes from main; re-read its remote identity before output.
    observed = observed_diagnostics(root, ref)
    if api.request('branches/main')['commit']['sha'] != ref:
        raise ValueError('Main advanced during source review; rerun/review before preparing a handoff.')
    values = dict(main=ref, merge=MERGE, receipt=receipt['html_url'],
                  observed=observed, checked=datetime.now(timezone.utc).isoformat(),
                  source_table='\n'.join(f'| `{r["path"]}` | `{r["blob"]}` | `{r["sha256"]}` |'
                                         for r in rows),
                  previous_table='\n'.join(f'| `{r["name"]}` | `{r["previous_sha256"]}` |' for r in rows),
                  check_links='; '.join(f'[{c["name"]}]({c["details_url"]}) PASS' for c in checks),
                  burst_hash=rows[0]['sha256'], diagnostics_hash=rows[1]['sha256'])
    return Template((root/'tools/pr34_deployment_handoff.md.tmpl').read_text()).substitute(values)


def fail_summary(comment):
    section = comment['body'].partition('## Failures / missing evidence')[2]
    section = section.split('Cancelled runs inspected:')[0].strip()
    return ('## BLOCKED — September 29 dawn acceptance FAIL\n\n' +
            f'Authoritative acceptance: {comment["html_url"]}\n\n' +
            (section[:14000] or 'Read the linked acceptance for the exact offending evidence.') +
            '\n\nNo deployment package or source staging was created. Resolve the acceptance failure '
            'before requesting a new deployment handoff. PointClearPC was not touched.')


def run(root, api, event):
    comments = api.pages(f'issues/{dawn.ISSUE}/comments')
    if any(trusted(c, MARKER) for c in comments):
        print('One-time follow-up already reported; no duplicate or deployment work.')
        return
    try:
        result = terminal(comments)
        if result is None:
            print('No terminal September 29 receipt; deployment remains on hold.')
            return
        comment, verdict = result
        if not validate_origin(api, comment, event):
            print('Await the matching acceptance producer completion; no handoff prepared.')
            return
        body = fail_summary(comment) if verdict == 'FAIL' else prepare(root, api, comment)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        body = ('## BLOCKED — deployment handoff not prepared\n\n' + str(exc) +
                '\n\nNo source package was staged and PointClearPC was not touched. '
                'Review this blocker before requesting another handoff.')
    body = MARKER + '\n@bentsmith4\n\n' + body
    body += '\n\nThis one-time follow-up is finished; later wake-ups will exit without repeating it.'
    # Recheck the durable marker; no blind POST retries on uncertain transport.
    if any(trusted(c, MARKER) for c in api.pages(f'issues/{dawn.ISSUE}/comments')):
        return
    posted = api.request(f'issues/{dawn.ISSUE}/comments', {'body': body})
    verified = api.request(f'issues/comments/{posted["id"]}')
    if verified.get('body') != body:
        raise ValueError('Follow-up comment readback mismatch; do not claim delivery.')
    print('One-time follow-up: ' + verified['html_url'])
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(body)


if __name__ == '__main__':
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    run(ROOT, dawn.GitHub(), event)

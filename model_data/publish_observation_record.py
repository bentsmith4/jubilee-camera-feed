#!/usr/bin/env python3
"""Append one immutable observation to current main without touching camera state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def git(repo, *args, data=None, env=None, check=True):
    p = subprocess.run(['git', '-C', str(repo), *args], input=data, capture_output=True, env=env)
    if check and p.returncode:
        raise RuntimeError('Git operation failed: '+args[0])
    return p


def publish(repo, output, attempts=3, before_push=None):
    from datetime import datetime
    capture = output.get('generated_from_capture_time_ct')
    if not capture or datetime.fromisoformat(capture).tzinfo is None:
        raise ValueError('Offset-aware capture identity required')
    if output.get('clean_training_negative_count') != 0 or output.get('production_action') != 'NO_CHANGE':
        raise ValueError('Observation logging cannot promote training labels or forecast weights')
    identity = hashlib.sha256(capture.encode()).hexdigest()[:24]
    name = 'model_data/observation_records/'+identity+'.json'
    raw = (json.dumps(output, sort_keys=True, indent=2)+'\n').encode()
    with tempfile.TemporaryDirectory(prefix='jubilee-observation-index-') as td:
        env=os.environ.copy();env['GIT_INDEX_FILE']=str(Path(td)/'index')
        for attempt in range(attempts):
            git(repo,'fetch','--quiet','origin','refs/heads/main')
            parent=git(repo,'rev-parse','FETCH_HEAD').stdout.decode().strip()
            prior=git(repo,'show',parent+':'+name,check=False)
            if prior.returncode==0:
                old=json.loads(prior.stdout)
                if old.get('input_hashes')!=output.get('input_hashes'):
                    raise ValueError('Capture identity reused with different inputs; preserve old record and investigate')
                return {'status':'already_recorded','record':name,'commit':parent}
            git(repo,'read-tree',parent,env=env)
            blob=git(repo,'hash-object','-w','--stdin',data=raw).stdout.decode().strip()
            git(repo,'update-index','--add','--cacheinfo','100644',blob,name,env=env)
            tree=git(repo,'write-tree',env=env).stdout.decode().strip()
            commit=git(repo,'commit-tree',tree,'-p',parent,'-m','Record scoped Jubilee observation '+capture).stdout.decode().strip()
            if before_push:before_push(attempt)
            if git(repo,'push','--quiet','origin',commit+':refs/heads/main',check=False).returncode==0:
                return {'status':'published','record':name,'commit':commit}
        raise RuntimeError('Concurrent update: bounded retries exhausted; no force push')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path('.'));p.add_argument('--input',type=Path,required=True)
    args=p.parse_args();print(json.dumps(publish(args.repo,json.loads(args.input.read_text()))))

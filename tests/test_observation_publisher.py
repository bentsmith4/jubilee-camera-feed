import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('observation_publisher',Path(__file__).resolve().parents[1]/'model_data/publish_observation_record.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class ObservationPublisherTests(unittest.TestCase):
    def test_retry_preserves_new_camera_commit_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);remote=root/'remote.git';repo=root/'repo';other=root/'other'
            def run(*args,cwd=None):return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.DEVNULL).decode().strip()
            run('init','--bare',str(remote));run('clone',str(remote),str(repo))
            for p in [repo]:
                run('config','user.name','test',cwd=p);run('config','user.email','test@example.com',cwd=p)
            run('checkout','-b','main',cwd=repo);(repo/'status.json').write_text('old')
            run('add','.',cwd=repo);run('commit','-m','base',cwd=repo);run('push','origin','main',cwd=repo)
            run('clone','--branch','main',str(remote),str(other))
            run('config','user.name','test',cwd=other);run('config','user.email','test@example.com',cwd=other)
            def concurrent(attempt):
                if attempt==0:
                    (other/'status.json').write_text('new camera')
                    run('add','.',cwd=other);run('commit','-m','new camera',cwd=other);run('push','origin','main',cwd=other)
            output={'generated_from_capture_time_ct':'2026-09-07T06:20:00-05:00','input_hashes':{'status':'a'},'clean_training_negative_count':0,'production_action':'NO_CHANGE'}
            result=mod.publish(repo,output,before_push=concurrent)
            self.assertEqual(result['status'],'published')
            run('fetch','origin','main',cwd=repo)
            self.assertEqual(run('show','FETCH_HEAD:status.json',cwd=repo),'new camera')
            self.assertEqual(json.loads(run('show','FETCH_HEAD:'+result['record'],cwd=repo)),output)
            self.assertEqual(mod.publish(repo,output)['status'],'already_recorded')
            output['input_hashes']={'status':'different'}
            with self.assertRaises(ValueError):mod.publish(repo,output)
            self.assertEqual((repo/'status.json').read_text(),'old')

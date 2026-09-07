import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))
import importlib.util, json, subprocess, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import publish_github as p

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / 'remote.git'
        self.repo = self.base / 'jubilee-camera-feed'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], capture_output=True, check=True)
        subprocess.run(['git', 'init', '-b', 'main', str(self.repo)], capture_output=True, check=True)
        for k,v in [('user.name','Test'),('user.email','test@example.invalid')]:
            p.git(self.repo,'config',k,v)
        (self.repo/'model.py').write_text('model v1')
        (self.repo/'montrose_pier_boat.jpg').write_bytes(b'old')
        p.git(self.repo,'add','.')
        p.git(self.repo,'commit','-m','model')
        self.original = p.git(self.repo,'rev-parse','HEAD').stdout.strip()
        p.git(self.repo,'remote','add','origin',str(self.remote))
        p.git(self.repo,'push','origin','main')
        self.frames = self.base/'frames'
        self.frames.mkdir()
        self.doc = {'capture_time_ct':datetime.now(timezone.utc).isoformat(),'cameras':{}}
        self.save()

    def save(self):
        for n in p.METADATA:
            (self.frames/n).write_text(json.dumps(self.doc))

    def test_ancestry_and_dirty_checkout_preserved(self):
        (self.repo/'model.py').write_text('uncommitted model')
        p.git(self.repo,'add','model.py')
        before = p.git(self.repo,'diff','--cached').stdout
        commit = p.publish(self.base)
        self.assertEqual(p.git(self.repo,'show',commit+':model.py').stdout,b'model v1')
        self.assertEqual(p.git(self.repo,'diff','--cached').stdout,before)
        self.assertEqual(p.git(self.repo,'rev-parse','HEAD').stdout.strip(),self.original)
        p.git(self.repo,'merge-base','--is-ancestor',self.original.decode(),commit)
        self.assertNotEqual(p.git(self.repo,'show',commit+':montrose_pier_boat.jpg',check=False).returncode,0)

    def test_concurrent_model_update_preserved(self):
        def race(attempt):
            if attempt == 0:
                (self.repo/'model.py').write_text('model v2')
                p.git(self.repo,'add','model.py')
                p.git(self.repo,'commit','-m','concurrent model update')
                p.git(self.repo,'push','origin','main')
        commit = p.publish(self.base,before_push=race)
        self.assertEqual(p.git(self.repo,'show',commit+':model.py').stdout,b'model v2')
        p.git(self.repo,'merge-base','--is-ancestor','HEAD',commit)

    def test_private_camera_refused(self):
        self.doc['cameras']['unapproved_camera']={'ok':False}
        self.save()
        with self.assertRaises(ValueError):p.publish(self.base)

    def test_future_and_stale_refused(self):
        for delta in [timedelta(hours=2),timedelta(hours=-2)]:
            self.doc['capture_time_ct']=(datetime.now(timezone.utc)+delta).isoformat()
            self.save()
            with self.assertRaises(ValueError):p.publish(self.base)

    def test_mismatch_refused(self):
        (self.frames/'vision.json').write_text('{}')
        with self.assertRaises(ValueError):p.publish(self.base)

    def test_signed_url_refused(self):
        self.doc['error']='rtsp://secret'
        self.save()
        with self.assertRaises(ValueError):p.publish(self.base)

if __name__=='__main__':unittest.main()

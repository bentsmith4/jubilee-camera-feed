import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_runtime"))
import io, unittest, tempfile, json
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from archive_integrity import freeze,VerifiedStore
from camera_lock import serialized
import threading,time

class Tests(unittest.TestCase):
    def test_failed_upload_verification(self):
        class Bad:
            def put_object(self,**kw):pass
            def get_object(self,**kw):return {'Body':io.BytesIO(b'corrupted')}
        with self.assertRaises(ValueError):VerifiedStore(Bad()).put_object(Bucket='test',Key='x',Body=b'good')
    def test_snapshot_and_private_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); frames=base/'frames'; frames.mkdir()
            doc={'capture_time_ct':datetime.now(timezone.utc).isoformat(),'cameras':{}}
            for name in ['status.json','vision.json','burst_status.json']:(frames/name).write_text(json.dumps(doc))
            target,seal=freeze(base)
            self.assertEqual(freeze(base)[1],seal)
            self.assertTrue((target/'capture_manifest.json').exists())
            doc['cameras']['montrose_shoreline']={'ok':False}
            (frames/'status.json').write_text(json.dumps(doc))
            with self.assertRaises(ValueError):freeze(base)
    def test_lock_serializes_and_releases_on_error(self):
        active=0; maximum=0
        @serialized
        def capture(device,fail=False):
            nonlocal active,maximum
            active+=1; maximum=max(active,maximum)
            try:
                time.sleep(.1)
                if fail:raise ValueError('simulated')
            finally:active-=1
        device={'name':'test-device'}
        threads=[threading.Thread(target=capture,args=(device,)) for _ in range(3)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(maximum,1)
        with self.assertRaises(ValueError):capture(device,True)
        capture(device)
if __name__=='__main__':unittest.main()

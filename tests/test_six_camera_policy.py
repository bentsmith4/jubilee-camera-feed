import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"desktop_runtime"))
import unittest
from camera_policy import CAMERA_IDS
import publish_github
from archive_integrity import PUBLIC_CAMERAS
class Policy(unittest.TestCase):
    def test_same_six_allowlisted(self):
        self.assertEqual(len(CAMERA_IDS),6)
        self.assertIn('montrose_shoreline',CAMERA_IDS)
        self.assertEqual(set(publish_github.CAMERAS),PUBLIC_CAMERAS)
        publish_github.validate_private({'cameras':{'montrose_shoreline':{'ok':False}}})

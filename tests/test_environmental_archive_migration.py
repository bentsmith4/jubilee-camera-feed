"""J04 migration failure-injection tests; no network or production credentials."""
import gzip
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration', ROOT/'model_data/environmental_archive_migration.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StoreError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class Store:
    def __init__(self):
        self.objects, self.puts = {}, 0
        self.read_error = None
        self.corrupt_after_put = False
        self.race = False

    def get_object(self, Bucket, Key):
        if self.read_error:
            raise StoreError(self.read_error)
        if Key not in self.objects:
            raise StoreError('NoSuchKey')
        return {'Body': io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert IfNoneMatch == '*'
        assert ContentType == 'application/gzip'
        self.puts += 1
        if self.race:
            self.objects[Key] = Body
            raise StoreError('PreconditionFailed')
        if Key in self.objects:
            raise StoreError('PreconditionFailed')
        self.objects[Key] = b'corrupt' if self.corrupt_after_put else Body


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Offline test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.raw = b'{"original_observation":42}\n'
        self.data = gzip.compress(self.raw, mtime=0)
        self.path = m.ARCHIVE+'asos/'+m.sha(self.raw)+'.json.gz'
        target = self.root/self.path
        target.parent.mkdir(parents=True)
        target.write_bytes(self.data)
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.catalog = m.inventory(self.root)
        self.store = Store()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.STDOUT)

    def mirror(self):
        return m.mirror(self.root, self.catalog, self.store, 'environmental-test')

    def test_roundtrip_preserves_original_bytes_and_both_hashes(self):
        receipt = self.mirror()
        self.assertEqual(receipt['status'], 'ALL_OBJECTS_GET_VERIFIED')
        destination = Path(self.tmp.name)/'restore'
        m.restore(self.catalog, self.store, 'environmental-test', destination)
        self.assertEqual((destination/self.path).read_bytes(), self.data)
        self.assertEqual(gzip.decompress((destination/self.path).read_bytes()), self.raw)
        self.assertFalse(receipt['production_cutover'])

    def test_resumption_does_not_overwrite(self):
        self.mirror()
        self.mirror()
        self.assertEqual(self.store.puts, 1)

    def test_dirty_checkout_does_not_change_pinned_inventory_or_mirror(self):
        (self.root/self.path).write_bytes(b'dirty')
        self.assertEqual(m.inventory(self.root), self.catalog)
        self.mirror()
        self.assertEqual(next(iter(self.store.objects.values())), self.data)

    def test_wrong_raw_hash_fails_inventory(self):
        (self.root/self.path).write_bytes(gzip.compress(b'wrong'))
        self.git('add', '.')
        self.git('commit', '-qm', 'bad bytes')
        with self.assertRaisesRegex(ValueError, 'historical raw hash'):
            m.inventory(self.root)

    def test_existing_corruption_is_not_overwritten(self):
        key = self.catalog['objects'][0]['object_key']
        self.store.objects[key] = b'broken'
        with self.assertRaises(Exception):
            self.mirror()
        self.assertEqual(self.store.puts, 0)
        self.assertEqual(self.store.objects[key], b'broken')

    def test_access_denied_never_becomes_missing(self):
        self.store.read_error = 'AccessDenied'
        with self.assertRaises(StoreError):
            self.mirror()
        self.assertEqual(self.store.puts, 0)

    def test_timeout_never_becomes_missing(self):
        with patch.object(self.store, 'get_object', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                self.mirror()
        self.assertEqual(self.store.puts, 0)

    def test_readback_corruption_blocks_success_receipt(self):
        self.store.corrupt_after_put = True
        with self.assertRaises(Exception):
            self.mirror()

    def test_conditional_race_requires_verified_winner(self):
        self.store.race = True
        self.assertEqual(self.mirror()['object_count'], 1)

    def test_catalog_tampering_blocks_all_writes(self):
        self.catalog['objects'][0]['object_key'] = 'camera/latest.jpg'
        with self.assertRaisesRegex(ValueError, 'immutable object key'):
            self.mirror()
        self.assertEqual(self.store.puts, 0)

    def test_manifest_hash_mismatch_fails_closed(self):
        import json
        manifest = self.root/'model_data/test_manifest.json'
        manifest.write_text(json.dumps({'raw_path':self.path.removeprefix('model_data/'),
                                       'raw_sha256':m.sha(self.raw)}))
        self.git('add', '.')
        self.git('commit', '-qm', 'manifest')
        catalog = m.inventory(self.root)
        self.assertEqual(len(m.audit_manifest_references(self.root, catalog)), 1)
        manifest.write_text(json.dumps({'raw_path':self.path.removeprefix('model_data/'),
                                       'raw_sha256':'0'*64}))
        self.git('add', '.')
        self.git('commit', '-qm', 'mismatched manifest')
        with self.assertRaisesRegex(ValueError, 'manifest hash mismatch'):
            m.audit_manifest_references(self.root, m.inventory(self.root))

    def test_empty_and_duplicate_catalog_rejected(self):
        for entries in ([], self.catalog['objects']*2):
            bad = dict(self.catalog, objects=entries)
            with self.assertRaises(ValueError):
                m.validate_catalog(bad)

    def test_restore_never_overwrites_existing_directory(self):
        self.mirror()
        with self.assertRaises(FileExistsError):
            m.restore(self.catalog, self.store, 'environmental-test', self.root)
        self.assertEqual((self.root/self.path).read_bytes(), self.data)

    def test_path_escape_and_camera_class_rejected(self):
        for path in ('../escape.gz', m.ARCHIVE+'asos/../../escape.gz',
                     m.ARCHIVE+'camera/'+m.sha(self.raw)+'.json.gz'):
            with self.assertRaises(ValueError):
                m.identity(path, self.data)

    def test_same_raw_different_gzip_bytes_have_distinct_keys(self):
        other = gzip.compress(self.raw, mtime=1234)
        a, b = m.identity(self.path, self.data), m.identity(self.path, other)
        self.assertEqual(a['raw_sha256'], b['raw_sha256'])
        self.assertNotEqual(a['object_key'], b['object_key'])

    def test_uncompressed_expansion_is_bounded(self):
        with patch.object(m, 'MAX_RAW', 4):
            with self.assertRaisesRegex(ValueError, 'expanded object'):
                m.identity(self.path, self.data)

    def test_truncated_get_rejected(self):
        self.mirror()
        key = self.catalog['objects'][0]['object_key']
        self.store.objects[key] = self.data[:-3]
        with self.assertRaises(Exception):
            m.restore(self.catalog, self.store, 'environmental-test', Path(self.tmp.name)/'bad')


if __name__ == '__main__':
    unittest.main()

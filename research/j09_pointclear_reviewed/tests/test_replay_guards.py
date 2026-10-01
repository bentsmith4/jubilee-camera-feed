"""Small synthetic rows test the replay verifier, not environmental accuracy."""
import csv
import gzip
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from validate_replay import verify_all_velocity_rows, verify_archive

AVAILABLE = '2016-01-07T15:38:00Z'


class ReplayGuardTests(unittest.TestCase):
    def fixture(self, root, overrides=None):
        row = dict(earth_east_mps='', earth_north_mps='', validated_current='False',
                   production_weight='0', coordinate_system='SHIP', available_at_utc=AVAILABLE,
                   velocity_frame='WATER_RELATIVE_TO_INSTRUMENT',
                   bottom_difference_status='RESEARCH_DIAGNOSTIC_NOT_VALIDATED')
        row.update(overrides or {})
        path = root / 'rows.csv.gz'
        with gzip.open(path, 'wt', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_preserved_gates_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(verify_all_velocity_rows(self.fixture(pathlib.Path(folder)), 1, AVAILABLE), 1)

    def test_every_gate_rejected_independently(self):
        invalid = dict(earth_east_mps='1', earth_north_mps='1', validated_current='True',
                       production_weight='0.1', coordinate_system='EARTH', available_at_utc='2010-08-18T00:00:00Z',
                       velocity_frame='ABSOLUTE', bottom_difference_status='VALIDATED')
        for field, value in invalid.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                path = self.fixture(pathlib.Path(folder), {field: value})
                with self.assertRaisesRegex(ValueError, 'production_gate_violation'):
                    verify_all_velocity_rows(path, 1, AVAILABLE)

    def test_truncated_output_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'row_count_mismatch'):
                verify_all_velocity_rows(self.fixture(pathlib.Path(folder)), 2, AVAILABLE)

    def test_wrong_archive_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'archive.zip'
            path.write_bytes(b'wrong archive')
            manifest = {'archive': {'bytes': len(b'wrong archive'), 'sha256': '0' * 64}}
            with self.assertRaisesRegex(ValueError, 'acquired_archive_hash_mismatch'):
                verify_archive(path, manifest)


if __name__ == '__main__':
    unittest.main()

"""Opt-in checks using the real archive and freshly decoded full results.

No skips: ADCP_ARCHIVE and ADCP_RESULTS must be provided.
"""
import gzip
import csv
import pathlib
import os
import struct
import sys
import unittest
import zipfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ingest_ship_channel as m
ARCHIVE = pathlib.Path(os.environ['ADCP_ARCHIVE'])
RESULTS = pathlib.Path(os.environ['ADCP_RESULTS'])

class ActualPD0FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ARCHIVE) as z:
            data=z.read('20100818_transect/20100818_transect_000r.000')
        cls.packet=data[:m.U16(data,2)+2]
        _,_,cls.blocks=next(m.pd0_packets(cls.packet))
    def test_real_packet_geometry_and_non_earth_frame(self):
        meta,rows=m.decode_ensemble(self.blocks)
        self.assertEqual(meta['ensemble_number'],9)
        self.assertEqual(meta['rtc_native_naive'],'2010-08-18T09:34:25.760000')
        self.assertEqual(meta['rtc_timezone'],'UNKNOWN_DO_NOT_LOCALIZE')
        self.assertEqual(meta['coordinate_system'],'SHIP')
        self.assertEqual(meta['frequency_khz'],1200)
        self.assertEqual(meta['orientation'],'DOWN')
        self.assertEqual(meta['beam_angle_deg'],20)
        self.assertEqual(meta['cell_size_m'],0.5)
        self.assertEqual(meta['first_bin_center_from_transducer_m'],1.56)
        self.assertEqual(rows[-1]['distance_from_transducer_m'],21.06)
        self.assertEqual(rows[0]['water_v1_mps'],0.154)
        self.assertEqual(rows[0]['water_v2_mps'],-2.391)
        self.assertTrue(all(r['earth_east_mps'] is None and r['earth_north_mps'] is None for r in rows))
        self.assertTrue(all(not r['validated_current'] and r['production_weight']==0 for r in rows))
    def test_corrupt_packet_rejected(self):
        data=bytearray(self.packet);data[200]^=1
        with self.assertRaisesRegex(ValueError,'checksum_failed'): list(m.pd0_packets(data))
    def test_truncated_packet_rejected(self):
        with self.assertRaisesRegex(ValueError,'truncated'): list(m.pd0_packets(self.packet[:-1]))
    def test_bad_offset_rejected_even_after_rechecksumming(self):
        data=bytearray(self.packet);struct.pack_into('<H',data,6,1)
        struct.pack_into('<H',data,len(data)-2,sum(data[:-2])&65535)
        with self.assertRaisesRegex(ValueError,'invalid_pd0_offsets'): list(m.pd0_packets(data))
    def test_missing_velocity_block_fails_closed(self):
        blocks=dict(self.blocks);del blocks[256]
        with self.assertRaisesRegex(ValueError,'profile_length_mismatch'): m.decode_ensemble(blocks)
    def test_sentinel_does_not_become_large_velocity(self):
        blocks=dict(self.blocks);v=bytearray(blocks[256]);struct.pack_into('<h',v,2,-32768);blocks[256]=bytes(v)
        _,rows=m.decode_ensemble(blocks)
        self.assertIsNone(rows[0]['water_v1_mps'])
        self.assertIsNone(rows[0]['water_minus_bottom_v1_mps'])
        self.assertIn('MISSING_WATER_COMPONENT',rows[0]['qc_flags'])
    def test_bottom_flags_do_not_create_surface_depth(self):
        meta,rows=m.decode_ensemble(self.blocks)
        self.assertEqual(meta['native_transducer_depth_setting_m'],0)
        self.assertIn('CONSERVATIVE_SIDELOBE_RISK',rows[-1]['qc_flags'])
        self.assertNotIn('depth_below_surface_m',rows[0])

class ArtifactTests(unittest.TestCase):
    def test_every_normalized_vector_keeps_production_gate(self):
        with gzip.open(RESULTS/'velocity_bins.csv.gz','rt',encoding='utf8') as f:
            count=0
            for r in csv.DictReader(f):
                self.assertEqual(r['earth_east_mps'],'')
                self.assertEqual(r['earth_north_mps'],'')
                self.assertEqual(r['validated_current'],'False')
                self.assertEqual(r['production_weight'],'0')
                self.assertEqual(r['coordinate_system'],'SHIP')
                self.assertEqual(r['available_at_utc'],'2016-01-07T15:38:00Z')
                count+=1
        self.assertEqual(count,248400)

if __name__=='__main__': unittest.main(verbosity=2)

"""Lightweight NMEA examples; no archive download or environmental acceptance."""
import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import ingest_ship_channel as m

def sentence(body):
    checksum = 0
    for value in body.encode('ascii'):
        checksum ^= value
    return '$' + body + '*' + format(checksum, '02X')

class NavigationTests(unittest.TestCase):
    def test_known_real_rmc_date_coordinates_and_knots(self):
        r=m.parse_rmc('$GPRMC,153434,A,3041.9155,N,08802.2400,W,5.9,162.9,271010,1.0,W,A*11')
        self.assertEqual(r['observed_at_utc'],'2010-10-27T15:34:34+00:00')
        self.assertAlmostEqual(r['latitude'],30+41.9155/60)
        self.assertAlmostEqual(r['longitude'],-(88+2.24/60))
        self.assertAlmostEqual(r['vessel_speed_over_ground_mps'],3.035222222222222)
    def test_corrupt_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum_fail'):
            m.parse_rmc('$GPRMC,153434,A,3041.9155,N,08802.2400,W,5.9,162.9,271010,1.0,W,A*10')
    def test_missing_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum_missing'):
            m.parse_rmc('$GPRMC,153434,A,3041.9155,N,08802.2400,W,5.9,162.9,271010,1.0,W,A')
    def test_navigation_warning_rejected_even_with_valid_checksum(self):
        with self.assertRaisesRegex(ValueError,'navigation_warning'):
            m.parse_rmc(sentence('GPRMC,153434,V,3041.9155,N,08802.2400,W,5.9,162.9,271010,1.0,W,A'))
    def test_invalid_minutes_and_hemisphere_rejected(self):
        for value,hemisphere,lat in [('3060.1','N',True),('9000.1','N',True),('3041','E',True)]:
            with self.assertRaises(ValueError): m.coordinate(value,hemisphere,lat)
    def test_fractional_utc_time(self):
        self.assertEqual(m.nmea_time(dt.date(2010,8,18),'190614.25').microsecond,250000)


if __name__ == '__main__': unittest.main()

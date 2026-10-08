import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import model_data.ingest_arcos_realtime as collector
from datetime import datetime, timezone
from model_data.ingest_arcos_realtime import build_query, parse_response

CONFIG={
  "datasource_uid":"6Hvm4igSk","datasource_id":12,"aggregation_minutes":30,
  "source_ranges":{"water_temperature_c":[-5,45],"salinity_psu":[0,40],
    "dissolved_oxygen_percent":[0,200],"dissolved_oxygen_mg_l":[0,20],"turbidity_fnu":[-3,1000]},
  "stations":[{"station_key":"mp","station_id":"DISL_ARCOS_MP","name":"Meaher Park",
               "latitude":30.667152,"longitude":-87.936459,"role":"upper_bay_oxygen_loading_proxy"}]
}
STATION=CONFIG["stations"][0]

def payload(do_pct=3.1,do_mg=0.23,depth=0.0):
    return json.dumps({"results":{"A":{"status":200,"frames":[{"schema":{"fields":[
      {"name":"time"},{"name":"Water Temperature"},{"name":"Salinity"},
      {"name":"Dissolved Oxygen %"},{"name":"Dissolved Oxygen"},{"name":"Turbidity"},{"name":"Depth"}]},
      "data":{"values":[[1791450000000],[27.0],[11.4],[do_pct],[do_mg],[4.2],[depth]]}}]}}}).encode()

class ArcosRealtimeTests(unittest.TestCase):
    def test_empty_station_is_not_zero_measurement(self):
        self.assertEqual(parse_response(b'{"results":{"A":{"status":200,"frames":[]}}}',STATION,datetime.now(timezone.utc),CONFIG),[])

    def test_datasource_error_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_response(b'{"results":{"A":{"status":500,"error":"unavailable"}}}',STATION,datetime.now(timezone.utc),CONFIG)

    def test_nonfinite_measurement_is_not_admitted(self):
        rows=parse_response(payload(do_mg=float('nan')),STATION,datetime.now(timezone.utc),CONFIG)
        self.assertFalse(any(r['parameter']=='dissolved_oxygen_mg_l' for r in rows))

    def test_total_outage_clears_old_rows_and_declares_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=dict(CONFIG,poll_window_hours=6,freshness_minutes=60)
            (root/'sources.json').write_text(json.dumps(config))
            (root/'arcos_realtime_normalized.csv').write_text('old observations')
            with patch.object(collector,'HERE',root), patch.object(collector,'CONFIG',root/'sources.json'), patch.object(collector,'fetch',side_effect=OSError('offline')), patch('sys.argv',['collector']), patch('builtins.print'):
                collector.main()
            manifest=json.loads((root/'arcos_realtime_manifest.json').read_text())
            self.assertEqual(manifest['status'],'unavailable')
            self.assertEqual(manifest['normalized_rows'],0)
            self.assertEqual((root/'arcos_realtime_normalized.csv').read_text(),'')

    def test_allowlist_blocks_table_injection(self):
        with self.assertRaises(ValueError):
            build_query("mp;drop table x",datetime.now(timezone.utc),datetime.now(timezone.utc),CONFIG)

    def test_parse_low_do_preserves_units_and_zero_weight(self):
        rows=parse_response(payload(),STATION,datetime(2026,10,8,12,tzinfo=timezone.utc),CONFIG)
        by={r["parameter"]:r for r in rows}
        self.assertAlmostEqual(by["dissolved_oxygen_mg_l"]["value"],0.23)
        self.assertAlmostEqual(by["dissolved_oxygen_percent"]["value"],3.1)
        self.assertEqual(by["dissolved_oxygen_mg_l"]["unit"],"mg/L")
        self.assertEqual(by["dissolved_oxygen_mg_l"]["production_weight"],0.0)
        self.assertFalse(by["dissolved_oxygen_mg_l"]["is_direct_local_bottom_measurement"])

    def test_depth_zero_never_becomes_bottom_identity(self):
        rows=parse_response(payload(depth=0.0),STATION,datetime(2026,10,8,12,tzinfo=timezone.utc),CONFIG)
        depth=next(r for r in rows if r["parameter"]=="depth_field_m")
        self.assertEqual(depth["depth_geometry_status"],"UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION")

    def test_range_failure_is_retained_but_flagged(self):
        rows=parse_response(payload(do_mg=25.0),STATION,datetime(2026,10,8,12,tzinfo=timezone.utc),CONFIG)
        do=next(r for r in rows if r["parameter"]=="dissolved_oxygen_mg_l")
        self.assertEqual(do["qc_status"],"ARCOS_RANGE_CHECK_FAIL")

    def test_build_met_query_uses_allowlisted_station_table(self):
        q=build_query("mp",datetime(2026,10,8,11,tzinfo=timezone.utc),datetime(2026,10,8,12,tzinfo=timezone.utc),CONFIG,"met")
        sql=q["queries"][0]["rawSql"]
        self.assertIn("mp_met_min",sql)
        self.assertIn("Wind Direction",sql)

    def test_historical_geometry_does_not_create_current_bottom_identity(self):
        station=dict(STATION,historical_sensor_height_above_bottom_m=0.5,
                     historical_geometry_evidence_status="HISTORICAL_2019_ARCOS_OBSERVATION_GEOMETRY",
                     current_sensor_height_above_bed_verified=False)
        rows=parse_response(payload(),station,datetime(2026,10,8,12,tzinfo=timezone.utc),CONFIG)
        do=next(r for r in rows if r["parameter"]=="dissolved_oxygen_mg_l")
        self.assertEqual(do["historical_sensor_height_above_bottom_m"],0.5)
        self.assertFalse(do["is_direct_local_bottom_measurement"])
        self.assertEqual(do["depth_geometry_status"],"UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION")

if __name__=="__main__":
    unittest.main()

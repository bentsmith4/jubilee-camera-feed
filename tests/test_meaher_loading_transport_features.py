import csv, json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from model_data.build_meaher_loading_transport_features import build, transport_context

FIELDS=["source_id","source_stream","station_id","station_key","station_name","latitude","longitude","station_role","parameter","value","unit","observed_at","available_at","ingested_at","qc_status","source_qc_status","depth_geometry_status","historical_sensor_height_above_bottom_m","historical_geometry_evidence_status","is_direct_station_observation","is_direct_local_bottom_measurement","production_weight","source_url"]

def row(t,param,value,unit="mg/L"):
    return ["x","hydro","DISL_ARCOS_MP","mp","Meaher Park","30.66","-87.93","upper",param,str(value),unit,t,t,t,"ARCOS_RANGE_CHECK_PASS","SOURCE_QC_NOT_EXPOSED","UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION","0.5","RECENT","True","False","0.0","x"]

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/"model_data").mkdir()
        with (self.root/"model_data/arcos_realtime_normalized.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(FIELDS)
            for t,v in [("2026-10-08T10:00:00+00:00",1.2),("2026-10-08T10:30:00+00:00",0.8),("2026-10-08T11:00:00+00:00",0.4),("2026-10-08T11:30:00+00:00",0.2)]:
                w.writerow(row(t,"dissolved_oxygen_mg_l",v))
                w.writerow(row(t,"dissolved_oxygen_percent",v*10,"%"))
                w.writerow(row(t,"salinity_psu",10+v,"PSU"))
                w.writerow(row(t,"water_temperature_c",28+v,"degC"))
        with (self.root/"model_data/ngofs2_point_clear_nowcast_normalized.csv").open("w",newline="",encoding="utf-8") as f:
            fields=["source_id","source_class","station_name","station_index","station_index_method","station_distance_km","latitude","longitude","angle_to_shore_deg","total_depth_m","vertical_position","layer_index","sigma","parameter","value_or_status","unit","valid_at","model_initialized_at","available_at","ingested_at","source_url","shoreline_cell","production_weight"]
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            w.writerow(dict(zip(fields,["n","MODEL","Pt Clear",93,"nearest",0.3,30.4,-87.9,272,1.8,"bottom",39,-.98,"shoreward_current",0.03,"m/s","2026-10-08T11:00:00+00:00","2026-10-08T09:00:00+00:00","2026-10-08T11:05:00+00:00","2026-10-08T11:05:00+00:00","x","Point Clear",0.0])))
    def tearDown(self): self.tmp.cleanup()
    def test_loading_slopes_and_threshold_duration(self):
        out=build(self.root,"2026-10-08T11:30:00+00:00")
        self.assertEqual(out["status"],"RESEARCH_FEATURES_AVAILABLE")
        self.assertAlmostEqual(out["loading"]["dissolved_oxygen_mg_l"],0.2)
        self.assertLess(out["loading"]["oxygen_windows"]["1"]["slope_per_hour"],0)
        self.assertGreater(out["loading"]["minutes_below_do_mg_l"]["1.0"],0)
        self.assertEqual(out["loading"]["production_weight"],0.0)
    def test_transport_after_issue_is_excluded(self):
        rows=[{"source_class":"MODEL","parameter":"shoreward_current","vertical_position":"bottom","valid_at":"2026-10-08T12:00:00+00:00","available_at":"2026-10-08T12:01:00+00:00","value_or_status":"0.1","station_name":"Pt Clear"}]
        out=transport_context(rows,datetime(2026,10,8,11,30,tzinfo=timezone.utc))
        self.assertEqual(out["status"],"UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT")
    def test_stale_transport_is_unknown(self):
        rows=[{"source_class":"MODEL","parameter":"shoreward_current","vertical_position":"bottom","valid_at":"2026-10-08T01:00:00+00:00","available_at":"2026-10-08T01:05:00+00:00","value_or_status":"0.1","station_name":"Pt Clear"}]
        out=transport_context(rows,datetime(2026,10,8,11,30,tzinfo=timezone.utc))
        self.assertEqual(out["status"],"UNKNOWN_STALE_MODEL_TRANSPORT")
        self.assertIsNone(out["shoreward_current_m_s"])
    def test_historical_height_does_not_promote_bottom_identity(self):
        out=build(self.root,"2026-10-08T11:30:00+00:00")
        self.assertEqual(out["loading"]["historical_sensor_height_above_bottom_m"],0.5)
        self.assertEqual(out["loading"]["current_geometry_status"],"UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION")
        self.assertEqual(out["production_action"],"NO_CHANGE")

if __name__=="__main__": unittest.main()

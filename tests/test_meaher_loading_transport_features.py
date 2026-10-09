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
            fields="source_id,evidence_class,station_name,station_index,station_resolution_basis,station_distance_to_point_clear_km,lat,lon,source_lon,bathymetry_m,vertical_role,sigma_layer_index,sigma_value,parameter,value,unit,valid_at,model_initialized_at,available_at,ingested_at,source_url,shoreline_cell,production_weight".split(",")
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            w.writerow({"source_id":"noaa_ngofs2_point_clear_station", "evidence_class":"MODEL",
                        "station_name":"8733821 Pt Clear, MB", "vertical_role":"bottom",
                        "parameter":"shoreward_current", "value":"0.03", "unit":"m/s",
                        "valid_at":"2026-10-08T11:00:00+00:00",
                        "available_at":"2026-10-08T11:05:00+00:00", "production_weight":"0.0"})
    def tearDown(self): self.tmp.cleanup()
    def test_loading_slopes_and_threshold_duration(self):
        out=build(self.root,"2026-10-08T11:30:00+00:00")
        self.assertEqual(out["status"],"RESEARCH_FEATURES_AVAILABLE")
        self.assertAlmostEqual(out["loading"]["dissolved_oxygen_mg_l"],0.2)
        self.assertLess(out["loading"]["oxygen_windows"]["1"]["slope_per_hour"],0)
        self.assertGreater(out["loading"]["minutes_below_do_mg_l"]["1.0"],0)
        self.assertEqual(out["loading"]["production_weight"],0.0)
    def test_transport_after_issue_is_excluded(self):
        rows=[{"evidence_class":"MODEL","parameter":"shoreward_current","vertical_role":"bottom","valid_at":"2026-10-08T12:00:00+00:00","available_at":"2026-10-08T12:01:00+00:00","value":"0.1","station_name":"Pt Clear"}]
        out=transport_context(rows,datetime(2026,10,8,11,30,tzinfo=timezone.utc))
        self.assertEqual(out["status"],"UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT")
    def test_stale_transport_is_unknown(self):
        rows=[{"evidence_class":"MODEL","parameter":"shoreward_current","vertical_role":"bottom","valid_at":"2026-10-08T01:00:00+00:00","available_at":"2026-10-08T01:05:00+00:00","value":"0.1","station_name":"Pt Clear"}]
        out=transport_context(rows,datetime(2026,10,8,11,30,tzinfo=timezone.utc))
        self.assertEqual(out["status"],"UNKNOWN_STALE_MODEL_TRANSPORT")
        self.assertIsNone(out["shoreward_current_m_s"])
    def test_historical_height_does_not_promote_bottom_identity(self):
        out=build(self.root,"2026-10-08T11:30:00+00:00")
        self.assertEqual(out["loading"]["historical_sensor_height_above_bottom_m"],0.5)
        self.assertEqual(out["loading"]["current_geometry_status"],"UNKNOWN_GEOMETRY_DO_NOT_USE_FOR_BOTTOM_CLASSIFICATION")
        self.assertEqual(out["production_action"],"NO_CHANGE")

if __name__=="__main__": unittest.main()


class ProductionSchemaTests(unittest.TestCase):
    issue=datetime(2026,10,9,8,30,tzinfo=timezone.utc)
    def source(self, **changes):
        r=dict(evidence_class='MODEL',vertical_role='bottom',parameter='shoreward_current',
               value='0.03',unit='m/s',valid_at='2026-10-09T08:00:00+00:00',
               available_at='2026-10-09T08:05:00+00:00')
        r.update(changes)
        return r
    def test_fresh_transport_including_zero(self):
        for v in ('0.03','0','-0.03'):
            out=transport_context([self.source(value=v)],self.issue)
            self.assertEqual(out['status'],'KNOWN_ZERO_WEIGHT_MODEL_CONTEXT')
            self.assertEqual(out['shoreward_current_m_s'],float(v))
            self.assertEqual(out['production_weight'],0)
    def test_missing_and_nonfinite_values(self):
        for v in (None,'','unknown','NaN','inf'):
            out=transport_context([self.source(value=v)],self.issue)
            self.assertEqual(out['status'],'UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT')
    def test_future_availability_and_bad_timestamps(self):
        for changes in ({'available_at':'2026-10-09T08:31:00+00:00'},
                        {'valid_at':'2026-10-09T08:31:00+00:00'},
                        {'available_at':''},{'valid_at':None}):
            out=transport_context([self.source(**changes)],self.issue)
            self.assertEqual(out['status'],'UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT')
    def test_stale_retained_october_7_row(self):
        out=transport_context([self.source(valid_at='2026-10-07T09:00:00+00:00',
                                         available_at='2026-10-07T13:51:51+00:00')],self.issue)
        self.assertEqual(out['status'],'UNKNOWN_STALE_MODEL_TRANSPORT')
        self.assertIsNone(out['shoreward_current_m_s'])
    def test_freshness_boundary(self):
        for t,expected in [('05:30:00','KNOWN_ZERO_WEIGHT_MODEL_CONTEXT'),
                           ('05:29:59','UNKNOWN_STALE_MODEL_TRANSPORT')]:
            out=transport_context([self.source(valid_at='2026-10-09T'+t+'+00:00')],self.issue)
            self.assertEqual(out['status'],expected)
    def test_nonmodel_and_nonbottom_excluded(self):
        for changes in ({'evidence_class':'OBSERVED'},{'vertical_role':'surface'}):
            self.assertEqual(transport_context([self.source(**changes)],self.issue)['status'],
                             'UNKNOWN_NO_AVAILABLE_MODEL_TRANSPORT')

class AvailabilityGuardTests(FeatureTests):
    def test_meaher_unavailable_at_issue_is_unknown(self):
        p=self.root/'model_data/arcos_realtime_normalized.csv'
        with p.open() as f: rows=list(csv.DictReader(f))
        for r in rows: r['available_at']='2026-10-08T12:00:00+00:00'
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
        self.assertEqual(build(self.root,'2026-10-08T11:30:00+00:00')['status'],
                         'UNKNOWN_NO_MEAHER_DO_AT_ISSUE_TIME')
    def test_stale_transport_suppresses_interaction(self):
        out=build(self.root,'2026-10-09T08:30:00+00:00')
        self.assertEqual(out['transport']['status'],'UNKNOWN_STALE_MODEL_TRANSPORT')
        self.assertIsNone(out['interactions']['low_do_x_shoreward_transport'])
        self.assertEqual(out['production_action'],'NO_CHANGE')

class RetainedSourceFixtureTests(unittest.TestCase):
    def test_actual_source_fixture_stays_unknown(self):
        p=Path(__file__).parent/'fixtures/ngofs2_point_clear_nowcast_20261007.csv'
        with p.open() as f: rows=list(csv.DictReader(f))
        out=transport_context(rows,datetime(2026,10,9,8,30,tzinfo=timezone.utc))
        self.assertEqual(out['status'],'UNKNOWN_STALE_MODEL_TRANSPORT')
        self.assertEqual(out['age_minutes'],2850)
        self.assertIsNone(out['shoreward_current_m_s'])
    def test_actual_schema_accepts_fresh_available_guidance(self):
        p=Path(__file__).parent/'fixtures/ngofs2_point_clear_nowcast_20261007.csv'
        with p.open() as f: rows=list(csv.DictReader(f))
        rows[0].update(valid_at='2026-10-09T08:00:00+00:00',
                       available_at='2026-10-09T08:05:00+00:00')
        out=transport_context(rows,datetime(2026,10,9,8,30,tzinfo=timezone.utc))
        self.assertEqual(out['status'],'KNOWN_ZERO_WEIGHT_MODEL_CONTEXT')
        self.assertEqual(out['shoreward_current_m_s'],float(rows[0]['value']))

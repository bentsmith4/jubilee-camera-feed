"""ARCOS archive-to-current-state regressions using production-shaped Git fixtures."""
import csv
import io
import json
from datetime import timedelta
from pathlib import Path
import test_current_state_reconciliation as base
T0 = base.T0
from test_arcos_realtime_ingest import payload
from model_data.ingest_arcos_realtime import parse_response
import check_current_state_freshness as guard
import reconcile_current_state as builder

ROOT = Path(__file__).resolve().parents[1]

class ArcosIntegrationTests(base.ReconciliationTests):
    def arcos(self, age=10, do=0.23):
        cfg=json.loads((ROOT/'model_data/arcos_realtime_sources.json').read_text())
        self.f.write('model_data/arcos_realtime_sources.json',cfg)
        limits=self.f.read('model_data/sensor_contract.json')
        limits['freshness_minutes']['arcos_realtime']=60
        self.f.write('model_data/sensor_contract.json',limits)
        retrieved=T0-timedelta(minutes=1)
        raw=json.loads(payload(do_mg=do))
        raw['results']['A']['frames'][0]['data']['values'][0]=[int((T0-timedelta(minutes=age)).timestamp()*1000)]
        rows=parse_response(json.dumps(raw).encode(),cfg['stations'][0],retrieved,cfg)
        out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        self.f.write('model_data/arcos_realtime_normalized.csv',out.getvalue().encode())
        sha=self.f.archive('raw_arcos_realtime/mp_hydro.json.gz',raw)
        stations=[dict(station_id=cfg['stations'][0]['station_id'],status='complete',streams=[dict(stream='hydro',status='complete',raw_path='raw_arcos_realtime/mp_hydro.json.gz',raw_sha256=sha)])]
        stations += [dict(station_id=s['station_id'],status='empty',streams=[]) for s in cfg['stations'][1:]]
        self.f.write('model_data/arcos_realtime_manifest.json',dict(status='partial',retrieved_at_utc=retrieved.isoformat(),stations=stations,normalized_rows=len(rows)))
        self.commit('ARCOS fixture')

    def admitted(self, snapshot):
        return next(x for x in snapshot['input_rows'] if x['source']==builder.ARCOS)['parameter_admission']

    def test_arcos_partial_archive_integration_and_unavailable_stations(self):
        self.arcos()
        s,_=self.reconcile(T0)
        rows=self.admitted(s)
        do=next(x for x in rows if x.get('parameter')=='dissolved_oxygen_mg_l')
        self.assertEqual(do['value'],0.23)
        self.assertTrue(all(x['production_weight']==0 for x in rows))
        self.assertEqual(sum(x['value_status']=='SOURCE_UNAVAILABLE_OR_NO_HYDRO' for x in rows),len(json.loads((ROOT/'model_data/arcos_realtime_sources.json').read_text())['stations'])-1)
        self.assertTrue(all(x['value'] is None for x in rows if x['value_status']=='SOURCE_UNAVAILABLE_OR_NO_HYDRO'))

    def test_arcos_stale_observations_are_unknown(self):
        self.arcos(age=90)
        s,_=self.reconcile(T0)
        rows=[x for x in self.admitted(s) if x.get('parameter') and x.get('unit')]
        self.assertTrue(all(x['value'] is None and x['value_status']=='UNKNOWN_STALE' for x in rows))

    def test_arcos_rejected_latest_measurement_never_backfills(self):
        self.arcos(do=25)
        s,_=self.reconcile(T0)
        do=next(x for x in self.admitted(s) if x.get('parameter')=='dissolved_oxygen_mg_l')
        self.assertIsNone(do['value']);self.assertEqual(do['value_status'],'UNKNOWN_MISSING_OR_QC_REJECTED')

    def test_arcos_corrupt_archive_blocks_admission(self):
        self.arcos()
        self.f.write('model_data/raw_arcos_realtime/mp_hydro.json.gz',b'corrupt')
        self.commit('broken archive')
        with self.assertRaises((ValueError,OSError,EOFError)):
            builder.build(self.root,T0)

    def test_arcos_empty_station_archive_is_verified(self):
        self.arcos()
        path='raw_arcos_realtime/empty_hydro.json.gz'
        raw={'results':{'A':{'status':200,'frames':[]}}}
        sha=self.f.archive(path,raw)
        m=self.f.read('model_data/arcos_realtime_manifest.json')
        m['stations'][1]['streams']=[dict(stream='hydro',status='empty',raw_path=path,raw_sha256=sha)]
        self.f.write('model_data/arcos_realtime_manifest.json',m)
        self.commit('empty archive evidence')
        self.reconcile(T0)
        self.f.write('model_data/'+path,b'corrupt')
        self.commit('corrupt empty archive')
        with self.assertRaises((ValueError,OSError,EOFError)):
            builder.build(self.root,T0)

    def test_arcos_unavailable_manifest_keeps_unknown(self):
        self.arcos()
        self.f.write('model_data/arcos_realtime_manifest.json',dict(status='unavailable',retrieved_at_utc=(T0-timedelta(minutes=1)).isoformat(),stations=[],normalized_rows=0))
        self.commit('source unavailable')
        s,_=self.reconcile(T0)
        self.assertTrue(all(x['value'] is None for x in self.admitted(s)))

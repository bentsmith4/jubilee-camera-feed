#!/usr/bin/env python3
"""Score frozen year-held-out proxy comparisons only after coverage gates pass."""
import argparse
import csv
from datetime import date,timedelta
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
import audit


def ridge(train_x, train_y, test_x):
    x=np.asarray(train_x,dtype=float);z=np.asarray(test_x,dtype=float)
    mean=x.mean(axis=0);scale=x.std(axis=0);scale[scale==0]=1
    x=np.column_stack([np.ones(len(x)),(x-mean)/scale])
    z=np.column_stack([np.ones(len(z)),(z-mean)/scale])
    coef=np.linalg.solve(x.T@x+np.diag([0]+[1]*(x.shape[1]-1)),x.T@np.asarray(train_y))
    return z@coef,{'training_mean':mean.tolist(),'training_scale':scale.tolist(),'coefficients':coef.tolist()}


def paired_metrics(days, y, base, aug):
    y=np.asarray(y);b=np.asarray(base)-y;a=np.asarray(aug)-y
    blocks={}
    for d,be,ae in zip(days,b,a):
        block=(d-date(2018,5,1)).days//14
        v=blocks.setdefault(block,{'n':0,'sum_delta_squared_error':0.0})
        v['n']+=1;v['sum_delta_squared_error']+=float(ae*ae-be*be)
    for v in blocks.values():v['delta_mse']=v['sum_delta_squared_error']/v['n']
    vals=list(blocks.values());rng=np.random.default_rng(39)
    indices=rng.integers(0,len(vals),size=(10000,len(vals)))
    sums=np.array([v['sum_delta_squared_error'] for v in vals]);counts=np.array([v['n'] for v in vals])
    bootstrap=sums[indices].sum(axis=1)/counts[indices].sum(axis=1)
    return {'test_days':len(days),'baseline_rmse':float(np.sqrt(np.mean(b*b))),
            'augmented_rmse':float(np.sqrt(np.mean(a*a))),'baseline_mae':float(np.mean(abs(b))),
            'augmented_mae':float(np.mean(abs(a))),'delta_mse':float(np.mean(a*a-b*b)),
            'delta_mse_97_5_percent_block_percentile_interval':np.quantile(bootstrap,[.0125,.9875]).tolist(),
            'blocks':blocks,'uncertainty_caveat':'Approximate paired block resampling; adjacent blocks may remain dependent; not a transport-time confidence interval.'}


def build_rows(h,m,f,year,offsets,coverage):
    rows=[]
    for ds in coverage['dates']:
        d=date.fromisoformat(ds)
        x=[math.log(f[d]),h['temperature'][d]['mean'],h['salinity'][d]['mean'],
           h['water_height'][d]['mean'],h['water_height'][d]['range'],
           m['wind_vector'][d]['east'],m['wind_vector'][d]['north'],
           m['air_temperature'][d]['mean'],m['solar'][d]['mean']]
        phase=2*math.pi*d.timetuple().tm_yday/365.25
        rows.append({'day':d,'target':h['oxygen'][d]['median'],'base':x,
                     'lag':math.log(statistics.mean(f[d-timedelta(days=n)] for n in offsets)),
                     'calendar':[math.sin(phase),math.cos(phase)]})
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--cache-dir',type=Path,required=True)
    p.add_argument('--coverage',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);args=p.parse_args()
    manifest=json.loads(args.coverage.read_text());paths={}
    prereg=Path(__file__).with_name('PREREGISTRATION.md').read_bytes()
    if hashlib.sha256(prereg).hexdigest()!=manifest['preregistration_sha256']:raise ValueError('Preregistration mismatch')
    for key,meta in manifest['sources'].items():
        path=args.cache_dir/(hashlib.sha256(meta['url'].encode()).hexdigest()+'.raw')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Source hash mismatch: '+key)
        paths[key]=path
    data={}
    for year in audit.YEARS:
        h,_=audit.annual(paths[f'{year}_hydro'],audit.HYDRO,year,'hydro')
        m,_=audit.annual(paths[f'{year}_met'],audit.MET,year,'met');rr=[]
        for month in range(4,10):
            key=f'{year}_river_{month}'
            rr+=audit.normalize(json.loads(paths[key].read_text()),audit.stamp(manifest['generated_at_utc']),manifest['sources'][key]['url'])
        data[year]=(h,m,rr)
    result={'scope':'RESEARCH_ONLY_STATION_PROXY_REPLICATION','production_weight':0,'promotion_eligible':False,
            'preregistration_commit':manifest['preregistration_commit'],
            'coverage_sha256':hashlib.sha256(args.coverage.read_bytes()).hexdigest(),
            'target_unit':'oxygen percent saturation points','train_year':2017,'test_year':2018,'numpy_version':np.__version__,
            'feature_order':['log_same_day_discharge','water_temperature_mean','salinity_mean','water_height_mean','water_height_range','wind_east_mean','wind_north_mean','air_temperature_mean','solar_mean','calendar_sin/cos_when_requested','log_antecedent_discharge_augmented_only'],
            'comparisons':{},'interpretation':'Out-of-year station proxy association; no physical travel-time, bottom-state, event or operational forecast validation.'}
    predictions=[]
    for gauge,offsets in audit.WINDOWS.items():
        for strict in (False,True):
            suffix='_approved_not_estimated' if strict else ''
            key=gauge+suffix
            cs=[manifest['overlap'][f'{year}_{key}'] for year in audit.YEARS]
            if any(c['status']!='COVERAGE_PASS' for c in cs):
                result['comparisons'][key]={'status':'BLOCKED_BEFORE_FITTING','coverage_by_year':dict(zip(map(str,audit.YEARS),cs))};continue
            sets=[]
            for year,c in zip(audit.YEARS,cs):
                h,m,rr=data[year];f,_=audit.river(rr,gauge,strict)
                fresh=audit.overlap(h,m,f,year,offsets)
                if json.loads(json.dumps(fresh))!=c:raise ValueError('Coverage changed on replay')
                sets.append(build_rows(h,m,f,year,offsets,c))
            train,test=sets
            for calendar in (False,True):
                label=key+('_calendar' if calendar else '')
                tx=[r['base']+(r['calendar'] if calendar else []) for r in train]
                zx=[r['base']+(r['calendar'] if calendar else []) for r in test]
                ty=[r['target'] for r in train];zy=[r['target'] for r in test]
                base,bfit=ridge(tx,ty,zx)
                aug,afit=ridge([x+[r['lag']] for x,r in zip(tx,train)],ty,[x+[r['lag']] for x,r in zip(zx,test)])
                metrics=paired_metrics([r['day'] for r in test],zy,base,aug)
                result['comparisons'][label]={'status':'SCORED','training_days':len(train),'offset_days':offsets,
                    'metrics':metrics,'baseline_fit':bfit,'augmented_fit':afit}
                for r,b,a in zip(test,base,aug):predictions.append({'comparison':label,'date':r['day'].isoformat(),'observed_percent':r['target'],'baseline_percent':float(b),'augmented_percent':float(a)})
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    with (args.out_dir/'held_out_predictions.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['comparison','date','observed_percent','baseline_percent','augmented_percent']);w.writeheader();w.writerows(predictions)
    print(json.dumps({k: {'status':v['status'],**{f:v.get('metrics',{}).get(f) for f in ['baseline_rmse','augmented_rmse','delta_mse','delta_mse_97_5_percent_block_percentile_interval']}} for k,v in result['comparisons'].items()},indent=2))
if __name__=='__main__':main()

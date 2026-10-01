#!/usr/bin/env python3
"""Research-only, outcome-blind eligibility audit for the frozen PR39 replication.

No association/model fitting, forecasts, production writes, or target summaries.
Source bytes stay in a supplied cache; hashes and coverage are emitted locally.
"""
from __future__ import annotations
import argparse
import calendar
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
import urllib.parse
import urllib.request
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest_river_forcing import normalize

YEARS = (2017, 2018)
WINDOWS = {'02428400': [7,8,9,10,11,12,13], '02469761': [3,4,5,6]}
HYDRO = {'oxygen': ('dis_oxy1_avg','dis_oxy1flag',0,200),
         'temperature': ('watertemp1_avg','watertemp1flag',-5,45),
         'salinity': ('salinity1_avg','salinity1flag',0,40),
         'water_height': ('depth1_avg','depth1flag',0,float('inf'))}
MET = {'air_temperature': ('airtemp1','airtemp1flag',-10,50),
       'solar': ('solarrad1','solarrad1flag',0,1.5),
       'wind_direction': ('winddir1','winddir1flag',0,360),
       'wind_speed': ('windspeed1','windspeed1flag',0,30 / (1852/3600))}

def number(v):
    try:
        f=float(v)
        return f if math.isfinite(f) else None
    except (ValueError,TypeError): return None

def stamp(v):
    t=datetime.fromisoformat(v.replace('Z','+00:00'))
    if t.tzinfo is None: raise ValueError('Naive timestamp: do not guess timezone')
    return t.astimezone(timezone.utc)

def complete(times, minimum, gap_seconds):
    ts=sorted(set(times))
    if len(ts)<minimum: return False
    start=datetime.combine(ts[0].date(),datetime.min.time(),timezone.utc)
    if any(t.date()!=start.date() for t in ts): raise ValueError('Mixed UTC days')
    gaps=[(ts[0]-start).total_seconds(),(start+timedelta(days=1)-ts[-1]).total_seconds()]
    gaps += [(b-a).total_seconds() for a,b in zip(ts,ts[1:])]
    return max(gaps)<=gap_seconds

def download(item, cache):
    key,url=item
    path=cache / (hashlib.sha256(url.encode()).hexdigest()+'.raw')
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Jubilee-research-only/1.0'}),timeout=60) as r:
            payload=r.read(50_000_001)
        if len(payload)>50_000_000: raise ValueError('Source exceeds 50 MB bound')
        path.write_bytes(payload)
    payload=path.read_bytes()
    return key, path, {'url':url,'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),'acquired_at_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()}

def annual(path, specs, year, cadence):
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.endswith('.csv')]
        if len(names)!=1: raise ValueError('Expected one CSV member')
        raw=z.read(names[0])
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    required={'ts'} | {v for s in specs.values() for v in s[:2]}
    if not required.issubset(reader.fieldnames): raise ValueError('Required columns missing')
    points=defaultdict(dict); conflicts=defaultdict(set); counts=Counter(); flags=defaultdict(Counter)
    first=None;last=None
    for row in reader:
        counts['raw_rows']+=1
        t=stamp(row['ts']);first=min(first,t) if first else t;last=max(last,t) if last else t
        if t.year!=year or not 5<=t.month<=9: continue
        counts['season_rows']+=1
        for name,(field,flag,lo,hi) in specs.items():
            flags[name][row[flag]]+=1
            value=number(row[field])
            if number(row[flag])!=3 or value is None or not lo<=value<=hi or (name=='water_height' and value==0):
                counts[name+'_rejected_qc_or_range']+=1;continue
            if t in points[name]:
                counts[name+'_duplicate_timestamps']+=1
                if points[name][t]!=value: conflicts[name].add(t)
            points[name][t]=value
    daily={};summaries={}
    for name in specs:
        byday=defaultdict(list)
        for t,v in points[name].items():
            if t not in conflicts[name]: byday[t.date()].append((t,v))
        good={d:obs for d,obs in byday.items() if complete([t for t,v in obs],43 if cadence=='hydro' else 1296,3600 if cadence=='hydro' else 7200)}
        daily[name]={d: {'mean':statistics.mean(v for t,v in obs),'median':statistics.median(v for t,v in obs),
                         'range':max(v for t,v in obs)-min(v for t,v in obs)} for d,obs in good.items()}
        summaries[name]={'qualified_days':len(good),'qualified_rows':sum(len(o) for o in good.values()),
                         'conflicting_timestamps':len(conflicts[name]),'source_flags':dict(flags[name])}
    # Wind vectors must use paired minutes, not separately averaged directions.
    if cadence=='met':
        paired=defaultdict(list)
        for t,speed in points['wind_speed'].items():
            if t in points['wind_direction'] and t not in conflicts['wind_speed'] and t not in conflicts['wind_direction']:
                a=math.radians(points['wind_direction'][t]); s=speed*1852/3600
                paired[t.date()].append((t,-s*math.sin(a),-s*math.cos(a)))
        daily['wind_vector']={d:{'east':statistics.mean(o[1] for o in obs),'north':statistics.mean(o[2] for o in obs)}
                              for d,obs in paired.items() if complete([o[0] for o in obs],1296,7200)}
        summaries['wind_vector']={'qualified_days':len(daily['wind_vector'])}
    return daily, {'first_utc':first.isoformat(),'last_utc':last.isoformat(),'counts':dict(counts),
                   'variables':summaries,'member':names[0],'member_sha256':hashlib.sha256(raw).hexdigest(),
                   'schema':reader.fieldnames}

def river(rows, gauge, strict=False):
    good=[r for r in rows if r['station_id']==gauge and r['parameter_code']=='00060'
          and r['research_qc_eligible'] and r['method_identity_verified'] and r['unit'] in ('ft3/s','ft^3/s') and r['value']>0
          and (not strict or (not r['is_estimated'] and 'P' not in r['qualifiers'].split('|')))]
    methods=sorted(set(r['series_id'] for r in good))
    summary={'raw_discharge_rows':sum(r['station_id']==gauge and r['parameter_code']=='00060' for r in rows),
             'methods':methods,'estimated_rows':sum(r['is_estimated'] for r in good),
             'provisional_rows':sum('P' in r['qualifiers'].split('|') for r in good)}
    if len(methods)!=1: return {},dict(summary,status='AMBIGUOUS_OR_MISSING_METHOD')
    bytime=defaultdict(set)
    for r in good: bytime[stamp(r['observed_at_utc'])].add(r['value'])
    byday=defaultdict(list)
    for t,values in bytime.items():
        if len(values)==1: byday[t.date()].append((t,next(iter(values))))
    daily={d:statistics.mean(v for t,v in obs) for d,obs in byday.items() if complete([t for t,v in obs],22,7200)}
    return daily,dict(summary,status='AUDITED',qualified_days=len(daily),conflicting_timestamps=sum(len(v)>1 for v in bytime.values()))

def overlap(hydro,met,flow,year,offsets):
    start=date(year,5,1);days=[start+timedelta(days=i) for i in range(153)]
    missing=Counter();usable=[]
    for d in days:
        reasons=[name for name,v in {**hydro,**met}.items() if d not in v]
        if d not in flow: reasons.append('same_day_discharge')
        if any(d-timedelta(days=n) not in flow for n in offsets): reasons.append('antecedent_discharge')
        missing.update(reasons)
        if not reasons: usable.append(d)
    blocks=Counter((d-start).days//14 for d in usable)
    eligible=len(usable)>=60 and sum(n>=7 for n in blocks.values())>=6
    return {'status':'COVERAGE_PASS' if eligible else 'INSUFFICIENT_JOINT_COVERAGE',
            'common_days':len(usable),'testable_blocks':sum(n>=7 for n in blocks.values()),
            'block_day_counts':dict(blocks),'missing_days_by_requirement_nonexclusive':dict(missing),
            'dates':[d.isoformat() for d in usable]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--cache-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.cache_dir.mkdir(parents=True,exist_ok=True)
    urls={}
    for y in YEARS:
        for kind,stem in [('hydro','mp_hyd_sum'),('met','mp_met_min')]: urls[f'{y}_{kind}']=f'https://api.disl.edu/arcos/pregen/{stem}.{y}.csv.zip'
        for m in range(4,10):
            params={'format':'json','sites':'02428400,02469761','startDT':f'{y}-{m:02d}-01',
                    'endDT':f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]}','parameterCd':'00060','siteStatus':'all'}
            urls[f'{y}_river_{m}']='https://waterservices.usgs.gov/nwis/iv/?'+urllib.parse.urlencode(params)
    expected=json.loads(a.out.read_text()).get('sources',{}) if a.out.exists() else {}
    sources={};paths={};errors={}
    def fetch(item):
        try:return download(item,a.cache_dir)
        except Exception as e:return item[0],None,{'url':item[1],'error':str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key,path,meta in pool.map(fetch,urls.items()):
            if key in expected and 'sha256' in meta and meta['sha256']!=expected[key].get('sha256'):
                raise ValueError('Source changed since recorded manifest: '+key)
            sources[key]=meta
            if path is None:errors[key]=meta['error']
            else:paths[key]=path
    result={'scope':'RESEARCH_ONLY_INDEPENDENT_YEAR_COVERAGE','production_weight':0,'promotion_eligible':False,
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),'preregistration_commit':'20429b33a2449990cf5ffd971c34181c0d713a54',
            'preregistration_sha256':hashlib.sha256(Path(__file__).with_name('PREREGISTRATION.md').read_bytes()).hexdigest(),
            'sources':sources,'errors':errors,'annual':{},'overlap':{},'model_results_inspected':False}
    for y in YEARS:
        needed=[k for k in urls if k.startswith(str(y))]
        if any(k not in paths for k in needed):continue
        hydro,hm=annual(paths[f'{y}_hydro'],HYDRO,y,'hydro');met,mm=annual(paths[f'{y}_met'],MET,y,'met')
        result['annual'][str(y)]={'hydro':hm,'met':mm,'river':{}}
        rows=[]
        for m in range(4,10):
            k=f'{y}_river_{m}'
            rows.extend(normalize(json.loads(paths[k].read_text()),stamp(result['generated_at_utc']),urls[k]))
        for gauge,offsets in WINDOWS.items():
            for strict in (False,True):
                key=gauge+('_approved_not_estimated' if strict else '')
                flow,rs=river(rows,gauge,strict)
                result['annual'][str(y)]['river'][key]=rs
                result['overlap'][f'{y}_{key}']=overlap(hydro,met,flow,y,offsets)
    result['status']='ALL_COVERAGE_PASS' if len(result['overlap'])==8 and all(v['status']=='COVERAGE_PASS' for v in result['overlap'].values()) else 'PARTIAL_COVERAGE_CHECK_PER_COMPARISON'
    result['gate_scope']='Each comparison/sensitivity requires BOTH years to pass before that fit; unavailable sensitivities are reported, never imputed.'
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'errors':errors,'overlap':{k:{f:v[f] for f in ('common_days','testable_blocks','status')} for k,v in result['overlap'].items()}},indent=2))
if __name__=='__main__': main()

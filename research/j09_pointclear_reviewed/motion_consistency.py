"""Exploratory independent speed-magnitude diagnostic; not water-current QC."""
import argparse,bisect,collections,csv,datetime as dt,gzip,json,math,pathlib,statistics
ROOT=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--results-dir',type=pathlib.Path,default=ROOT/'results')
RESULTS=parser.parse_args().results_dir
def read(name):
    with gzip.open(RESULTS/name,'rt',encoding='utf8') as f:return list(csv.DictReader(f))
def metrics(rows):
    if not rows:return {'n':0}
    dif=[r['bottom_speed_mps']-r['gps_speed_mps'] for r in rows]
    bottom=[r['bottom_speed_mps'] for r in rows]
    gps=[r['gps_speed_mps'] for r in rows]
    correlation=(statistics.correlation(bottom,gps)
        if len(rows)>1 and len(set(bottom))>1 and len(set(gps))>1 else None)
    return {'n':len(rows),'median_signed_difference_mps':statistics.median(dif),
        'median_absolute_difference_mps':statistics.median(map(abs,dif)),
        'root_mean_square_difference_mps':math.sqrt(statistics.mean(d*d for d in dif)),
        'difference_over_0_5_mps_count':sum(abs(d)>0.5 for d in dif),
        'maximum_absolute_difference_mps':max(map(abs,dif)),
        'pearson_speed_correlation':correlation}
nav=collections.defaultdict(list)
for row in read('navigation_rmc.csv.gz'):
    if not row['qc_flags']:nav[row['survey_date']].append((dt.datetime.fromisoformat(row['observed_at_utc']).timestamp(),row))
for key in nav:nav[key].sort(key=lambda x:x[0])
pairs=[]; exclusions=collections.Counter()
for row in read('ensembles.csv.gz'):
    if not row['gps_gga_utc_candidate']:
        exclusions['no_embedded_valid_gga']+=1;continue
    if not row['external_rmc_nearest_seconds'] or float(row['external_rmc_nearest_seconds'])>3 or float(row['external_rmc_separation_m'])>30:
        exclusions['no_external_match_within_3s_30m']+=1;continue
    if not row['bottom_v1_mps'] or not row['bottom_v2_mps']:
        exclusions['missing_bottom_horizontal_velocity']+=1;continue
    candidates=nav[row['survey_date']];time=dt.datetime.fromisoformat(row['gps_gga_utc_candidate']).timestamp()
    stamps=[x[0] for x in candidates];k=bisect.bisect_left(stamps,time)
    _,gps=min((candidates[t] for t in (k-1,k) if 0<=t<len(candidates)),key=lambda x:abs(x[0]-time))
    pairs.append({'survey_date':row['survey_date'],'ensemble_number':row['ensemble_number'],
      'embedded_gga_utc':row['gps_gga_utc_candidate'],'rmc_utc':gps['observed_at_utc'],
      'pair_time_gap_s':float(row['external_rmc_nearest_seconds']),'pair_separation_m':float(row['external_rmc_separation_m']),
      'bottom_speed_mps':math.hypot(float(row['bottom_v1_mps']),float(row['bottom_v2_mps'])),
      'gps_speed_mps':float(gps['vessel_speed_over_ground_mps']),
      'bottom_error_mps':float(row['bottom_error_mps']) if row['bottom_error_mps'] else None,
      'coordinate_system':row['coordinate_system'],'velocity_validation_status':'RESEARCH_ONLY_NO_WATER_CURRENT_ACCEPTANCE'})
result={'status':'RESEARCH_DIAGNOSTIC_ONLY','pair_rule':'Embedded GGA versus external checksum-valid unflagged RMC <=3 s and <=30 m; bottom horizontal components present.',
 'meaning':'Bottom-relative speed magnitude and GPS vessel speed; scalar invariance avoids unverified heading rotation.',
 'limitations':['The PD0 ensemble averages water/bottom measurements; nearby GPS speed is not identically averaged.',
 'Serial observations are not independent trials. Correlation is not forecast skill.',
 'No check proves stationary bed, compass alignment, heading correction or true Earth water velocity.',
 'The 0.5 m/s count is an exploratory discrepancy summary, not an accepted source QC threshold.'],
 'all_pairs':metrics(pairs),'excluded_ensembles':dict(exclusions),
 'by_survey':{day:metrics([r for r in pairs if r['survey_date']==day]) for day in sorted(nav)},
 'production_action':'NO_CHANGE'}
(RESULTS/'motion_consistency.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
with (RESULTS/'motion_pairs.csv').open('w',newline='',encoding='utf8') as f:
    fields=['survey_date','ensemble_number','embedded_gga_utc','rmc_utc',
        'pair_time_gap_s','pair_separation_m','bottom_speed_mps','gps_speed_mps',
        'bottom_error_mps','coordinate_system','velocity_validation_status']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(pairs)
print(json.dumps(result['all_pairs']))

"""Offline, fail-closed GRIIDC Y1.x122.038:0002 research decoder.

No network, production writes, model weights, shore-normal projection or UTC
assignment to ADCP RTC. PD0 offsets/units: Teledyne WorkHorse manual Tables
31-39. GPS RMC: Garmin GPS 17x HVS section 4.2.7. All field offsets are zero-based.
"""
from __future__ import annotations
import argparse, bisect, collections, csv, datetime as dt, gzip, hashlib, io
import json, math, pathlib, re, statistics, struct, zipfile

DATASET = "Y1.x122.038:0002"
PUBLISHED = "2016-01-07T15:38:00Z"
COORDS = ("BEAM", "INSTRUMENT", "SHIP", "EARTH")
U16 = lambda b, p: struct.unpack_from("<H", b, p)[0]
I16 = lambda b, p: struct.unpack_from("<h", b, p)[0]
sha = lambda b: hashlib.sha256(b).hexdigest()

def nmea_fields(sentence):
    s = sentence.strip()
    if not s.startswith("$"):
        raise ValueError("not_nmea")
    body, star, tail = s[1:].partition("*")
    status = "MISSING"
    if star:
        if not re.fullmatch(r"[0-9A-Fa-f]{2}", tail):
            raise ValueError("malformed_nmea_checksum")
        checksum = 0
        for b in body.encode("ascii"):
            checksum ^= b
        status = "PASS" if checksum == int(tail, 16) else "FAIL"
    return body.split(","), status

def coordinate(value, hemisphere, is_latitude):
    if not re.fullmatch(r"\d{4,5}(?:\.\d+)?", value):
        raise ValueError("malformed_coordinate")
    if hemisphere not in (("N", "S") if is_latitude else ("E", "W")):
        raise ValueError("invalid_hemisphere")
    native = float(value)
    degrees, minutes = divmod(native, 100)
    limit = 90 if is_latitude else 180
    if minutes >= 60 or degrees > limit or (degrees == limit and minutes):
        raise ValueError("coordinate_out_of_range")
    return (degrees + minutes / 60) * (-1 if hemisphere in ("S", "W") else 1)

def nmea_time(date, clock):
    if not re.fullmatch(r"\d{6}(?:\.\d+)?", clock):
        raise ValueError("invalid_clock")
    sec = float(clock[4:])
    if sec >= 60:
        raise ValueError("unsupported_leap_second_or_bad_second")
    return dt.datetime.combine(date, dt.time(int(clock[:2]), int(clock[2:4]),
        int(sec), round((sec % 1) * 1e6)), tzinfo=dt.timezone.utc)

def parse_rmc(sentence):
    f, check = nmea_fields(sentence)
    if not f[0].endswith("RMC") or len(f) < 10:
        raise ValueError("not_complete_rmc")
    if check != "PASS":
        raise ValueError("rmc_checksum_" + check.lower())
    if f[2] != "A":
        raise ValueError("rmc_navigation_warning")
    if not re.fullmatch(r"\d{6}", f[9]):
        raise ValueError("invalid_rmc_date")
    y = int(f[9][4:]); y += 1900 if y >= 80 else 2000
    date = dt.date(y, int(f[9][2:4]), int(f[9][:2]))
    speed = float(f[7]) * 1852 / 3600
    course = float(f[8])
    if not (math.isfinite(speed) and 0 <= speed and 0 <= course < 360):
        raise ValueError("invalid_rmc_speed_or_course")
    return {"observed_at_utc": nmea_time(date, f[1]).isoformat(),
            "latitude": coordinate(f[3], f[4], True),
            "longitude": coordinate(f[5], f[6], False),
            "vessel_speed_over_ground_mps": speed,
            "vessel_course_true_deg": course, "nmea_checksum": check}

def haversine(lat1, lon1, lat2, lon2):
    p1,p2 = map(math.radians,(lat1,lat2)); dl=math.radians(lon2-lon1)
    a=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(a)))

def pd0_packets(data):
    """Reject an entire damaged stream; never search through corrupt payloads."""
    pos=0
    while pos < len(data):
        if data[pos:pos+2] != b"\x7f\x7f" or pos+6>len(data):
            raise ValueError(f"invalid_pd0_header_at_{pos}")
        n=U16(data,pos+2); count=data[pos+5]
        if n < 6+2*count or pos+n+2>len(data):
            raise ValueError(f"truncated_pd0_at_{pos}")
        p=data[pos:pos+n+2]
        if sum(p[:n]) & 0xffff != U16(p,n):
            raise ValueError(f"pd0_checksum_failed_at_{pos}")
        offsets=list(struct.unpack_from("<"+"H"*count,p,6))
        if offsets != sorted(set(offsets)) or any(x<6+2*count or x+2>n for x in offsets):
            raise ValueError(f"invalid_pd0_offsets_at_{pos}")
        blocks={}
        for start,end in zip(offsets,offsets[1:]+[n-2]):
            key=U16(p,start)
            if key in blocks or end<start+2:
                raise ValueError("invalid_pd0_block")
            blocks[key]=p[start:end]
        yield pos, p, blocks
        pos+=n+2

def unpack_vec(block, offset=2):
    if len(block)<offset+8: raise ValueError("short_vector")
    return [None if v==-32768 else v/1000 for v in struct.unpack_from("<4h",block,offset)]

def decode_ensemble(blocks):
    f=blocks.get(0,b""); v=blocks.get(128,b"")
    if len(f)<59 or len(v)<28: raise ValueError("short_leader")
    bins=f[9]; beams=f[8]
    if not 0<bins<=255 or beams!=4: raise ValueError("unsupported_beam_or_bin_count")
    for key,width in [(256,8),(512,4),(768,4),(1024,4)]:
        if len(blocks.get(key,b""))!=2+width*bins:
            raise ValueError(f"profile_length_mismatch_{key}")
    syscfg=U16(f,4); coord=COORDS[(f[25]>>3)&3]
    year=v[4]+(1900 if v[4]>=80 else 2000)
    rtc=dt.datetime(year,*v[5:10],v[10]*10000)
    b=blocks.get(1536,b"")
    bottom=[None]*4; ranges=[None]*4; bc=[]; bpg=[]
    if len(b)>=81:
        bottom=unpack_vec(b,24)
        ranges=[(U16(b,16+2*j)+(b[77+j]<<16))/100 or None for j in range(4)]
        bc=list(b[32:36]); bpg=list(b[40:44])
    meta={"ensemble_number":U16(v,2)+(v[11]<<16),"rtc_native_naive":rtc.isoformat(),
        "rtc_timezone":"UNKNOWN_DO_NOT_LOCALIZE", "coordinate_system":coord,
        "coordinate_transform_byte":f[25],"velocity_frame":"WATER_RELATIVE_TO_INSTRUMENT",
        "firmware":f"{f[2]}.{f[3]}", "frequency_khz":[75,150,300,600,1200,2400,None,None][syscfg&7],
        "orientation":"UP" if syscfg&128 else "DOWN", "beam_angle_deg": [15,20,30,None][(syscfg>>8)&3],
        "bins":bins,"cell_size_m":U16(f,12)/100,"blanking_m":U16(f,14)/100,
        "first_bin_center_from_transducer_m":U16(f,32)/100,
        "native_transducer_depth_setting_m":U16(v,16)/10,
        "heading_native_deg":U16(v,18)/100,"heading_alignment_deg":I16(f,26)/100,
        "heading_bias_deg":I16(f,28)/100,"pitch_deg":I16(v,20)/100,"roll_deg":I16(v,22)/100,
        "native_water_error_threshold_mps":U16(f,20)/1000,
        "native_water_correlation_threshold":f[17],"native_percent_good_threshold":f[19],
        "bottom_v1_mps":bottom[0],"bottom_v2_mps":bottom[1],"bottom_v3_mps":bottom[2],"bottom_error_mps":bottom[3],
        "bottom_range_min_m":min((x for x in ranges if x is not None),default=None),
        "bottom_ranges_m":ranges,"bottom_correlations":bc,"bottom_percent_good":bpg,
        "earth_water_velocity_available":False,"production_weight":0}
    rows=[]
    for j in range(bins):
        raw=unpack_vec(blocks[256],2+8*j); flags=[]
        distance=meta['first_bin_center_from_transducer_m']+j*meta['cell_size_m']
        corr=list(blocks[512][2+4*j:6+4*j]); pg=list(blocks[1024][2+4*j:6+4*j])
        if any(x is None for x in raw[:3]): flags.append("MISSING_WATER_COMPONENT")
        if raw[3] is None: flags.append("MISSING_ERROR_VELOCITY")
        elif meta['native_water_error_threshold_mps']>0 and abs(raw[3])>meta['native_water_error_threshold_mps']: flags.append("NATIVE_WATER_ERROR_LIMIT")
        if sum(x>=f[17] for x in corr)<3: flags.append("FEWER_THAN_THREE_BEAMS_PASS_NATIVE_CORRELATION")
        if any(x is None for x in bottom[:3]): flags.append("MISSING_BOTTOM_VELOCITY")
        if meta['bottom_range_min_m'] is None: flags.append("MISSING_BOTTOM_RANGE")
        elif meta['orientation']=="DOWN":
            if distance+meta['cell_size_m']/2>=meta['bottom_range_min_m']: flags.append("BIN_EDGE_AT_OR_BELOW_SHALLOWEST_BOTTOM")
            if meta['beam_angle_deg'] is not None and distance+meta['cell_size_m']/2>=meta['bottom_range_min_m']*math.cos(math.radians(meta['beam_angle_deg'])): flags.append("CONSERVATIVE_SIDELOBE_RISK")
        if max(abs(meta['pitch_deg']),abs(meta['roll_deg']))>20: flags.append("TILT_OUTSIDE_SPEC_RANGE")
        row={"bin_index_1based":j+1,"distance_from_transducer_m":round(distance,6),
             "water_v1_mps":raw[0],"water_v2_mps":raw[1],"water_v3_mps":raw[2],"water_error_mps":raw[3],
             "correlations":corr,"echo_intensities":list(blocks[768][2+4*j:6+4*j]),"percent_good":pg,
             "water_minus_bottom_v1_mps":None,"water_minus_bottom_v2_mps":None,
             "qc_flags":";".join(flags),"structural_screen_pass":not flags,
             "validated_current":False,"earth_east_mps":None,"earth_north_mps":None,"production_weight":0}
        # Algebraic research diagnostic only. No heading rotation, no magnetic
        # correction, no GPS replacement, no accepted environmental current.
        if coord in ("SHIP","EARTH") and not any(x is None for x in raw[:2]+bottom[:2]):
            row['water_minus_bottom_v1_mps']=round(raw[0]-bottom[0],6)
            row['water_minus_bottom_v2_mps']=round(raw[1]-bottom[1],6)
        rows.append(row)
    return meta,rows

def csv_gz(path, rows):
    if not rows: return
    with path.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as gz:
        with io.TextIOWrapper(gz,encoding='utf8',newline='') as out:
            w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
            for row in rows:
                w.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def summary_nums(values):
    values=[v for v in values if v is not None]
    return {"n":len(values),"min":min(values),"median":statistics.median(values),"max":max(values)} if values else {"n":0}

def run(archive, listing_dir, repo, out):
    out.mkdir(parents=True,exist_ok=True)
    acquired = dt.datetime.fromtimestamp(archive.stat().st_mtime,dt.timezone.utc).isoformat()
    z=zipfile.ZipFile(archive); names=z.namelist()
    if len(names)!=len(set(names)) or any(pathlib.PurePosixPath(n).is_absolute() or '..' in pathlib.PurePosixPath(n).parts for n in names):
        raise ValueError('unsafe_or_duplicate_archive_member')
    if len(names)!=68 or any(i.file_size>20_000_000 for i in z.infolist()): raise ValueError('unexpected_archive_shape')
    if z.testzip(): raise ValueError('zip_crc_failure')
    declared={r['name']:r['size'] for r in json.loads((listing_dir/'griidc-file-list.json').read_text()) if not r['isDirectory']}
    for p in sorted(listing_dir.glob('griidc-list-*.json')):
        prefix=p.stem.removeprefix('griidc-list-')
        declared.update({prefix+'/'+r['name']:r['size'] for r in json.loads(p.read_text()) if not r['isDirectory']})
    if declared != {i.filename:i.file_size for i in z.infolist()}: raise ValueError('provider_member_inventory_mismatch')
    manifest=[{'path':i.filename,'bytes':i.file_size,'sha256':sha(z.read(i.filename))} for i in sorted(z.infolist(),key=lambda i:i.filename)]
    hashes={r['path']:r['sha256'] for r in manifest}
    nav=[]; ensemble=[]; velocity=[]; surveys=[]
    target=json.loads((repo/'model_data/ngofs2_point_clear_nowcast_manifest.json').read_text())['station']
    for folder in sorted({n.split('/')[0] for n in names if '/' in n}):
        date=dt.datetime.strptime(folder[:8],'%Y%m%d').date()
        txt=next(n for n in names if n.startswith(folder+'/') and n.endswith('.TXT'))
        raw=next(n for n in names if n.startswith(folder+'/') and n.endswith('r.000'))
        config=next(n for n in names if n.startswith(folder+'/') and n.endswith('w.000'))
        config_text=z.read(config).decode('ascii')
        config_depth=float(re.search(r'ADCP Transducer Depth \[m\]=(.*)',config_text)[1])
        native_counts=collections.Counter(); rejections=collections.Counter(); nav_rows=[]
        for line_no,line_bytes in enumerate(z.read(txt).splitlines(),1):
            try: line=line_bytes.decode('ascii',errors='strict')
            except UnicodeDecodeError:
                native_counts['NON_ASCII_LINE_REJECTED']+=1
                continue
            if not line: continue
            if line.startswith('$'): native_counts[line.split(',')[0]]+=1
            else: native_counts['PARTIAL_OR_NON_NMEA_LINE']+=1
            if not line.startswith('$GPRMC,'): continue
            try: row=parse_rmc(line)
            except ValueError as exc: rejections[str(exc)]+=1; continue
            flags=[]
            if row['observed_at_utc'][:10]!=date.isoformat(): flags.append('DATE_DIFFERS_FROM_SURVEY_FOLDER')
            if not (30<=row['latitude']<=31 and -88.5<=row['longitude']<=-87.5): flags.append('OUTSIDE_BROAD_STUDY_REGION')
            if row['vessel_speed_over_ground_mps']>20: flags.append('SPEED_OVER_20_MPS_REVIEW')
            row.update(survey_date=date.isoformat(),source_file=txt,source_sha256=hashes[txt],source_line=line_no,
                       available_at_utc=PUBLISHED,ingested_at_utc=acquired,qc_flags=';'.join(flags))
            if nav_rows:
                prev=nav_rows[-1]; delta=(dt.datetime.fromisoformat(row['observed_at_utc'])-dt.datetime.fromisoformat(prev['observed_at_utc'])).total_seconds()
                dist=haversine(prev['latitude'],prev['longitude'],row['latitude'],row['longitude'])
                if delta<0: flags.append('NONMONOTONIC_GPS_TIME')
                elif delta==0 and dist>1: flags.append('CONFLICTING_POSITION_AT_SAME_TIME')
                elif delta>0 and dist/delta>20: flags.append('POSITION_JUMP_OVER_20_MPS_REVIEW')
                row['qc_flags']=';'.join(flags)
            nav_rows.append(row)
        nav.extend(nav_rows)
        sorted_nav=sorted(((dt.datetime.fromisoformat(r['observed_at_utc']).timestamp(),r) for r in nav_rows if not r['qc_flags']),key=lambda x:x[0])
        stamps=[x[0] for x in sorted_nav]
        times=[]; matching=[]; ens_start=len(ensemble); vel_start=len(velocity)
        for offset,packet,blocks in pd0_packets(z.read(raw)):
            meta,rows=decode_ensemble(blocks)
            meta.update(survey_date=date.isoformat(),source_file=raw,source_sha256=hashes[raw],byte_offset=offset,
                        available_at_utc=PUBLISHED,ingested_at_utc=acquired,configured_transducer_depth_m=config_depth)
            meta.update(gps_gga_utc_candidate=None,gps_date_basis='SURVEY_FOLDER_NOT_RTC',gps_latitude=None,gps_longitude=None,
                        gps_fix_quality=None,gps_checksum='NOT_PRESENT',gps_to_rtc_seconds=None,
                        external_rmc_nearest_seconds=None,external_rmc_separation_m=None)
            # Embedded GGA is covered by the complete PD0 checksum even when its
            # own NMEA checksum was omitted by WinRiver. Preserve this distinction.
            for b in blocks.values():
                m=re.search(rb'\$GPGGA,[^\r\n\x00]+',b)
                if not m: continue
                fields,check=nmea_fields(m[0].decode('ascii'))
                meta['gps_checksum']=check
                try:
                    if len(fields)<7 or int(fields[6])==0 or check=='FAIL': break
                    gps=nmea_time(date,fields[1])
                    meta['gps_gga_utc_candidate']=gps.isoformat();meta['gps_fix_quality']=int(fields[6])
                    meta['gps_latitude']=coordinate(fields[2],fields[3],True);meta['gps_longitude']=coordinate(fields[4],fields[5],False)
                    rtc=dt.datetime.fromisoformat(meta['rtc_native_naive']).replace(tzinfo=dt.timezone.utc)
                    # Numerical clock offset diagnostic, explicitly NOT localization.
                    lag=(gps-rtc).total_seconds();meta['gps_to_rtc_seconds']=lag;times.append(lag)
                    k=bisect.bisect_left(stamps,gps.timestamp())
                    opts=[sorted_nav[t] for t in [k-1,k] if 0<=t<len(sorted_nav)]
                    if opts:
                        stamp,r=min(opts,key=lambda q:abs(q[0]-gps.timestamp()))
                        delta=abs(stamp-gps.timestamp()); sep=haversine(meta['gps_latitude'],meta['gps_longitude'],r['latitude'],r['longitude'])
                        meta['external_rmc_nearest_seconds']=delta;meta['external_rmc_separation_m']=sep
                        if delta<=3 and sep<=30: matching.append(meta['ensemble_number'])
                except (ValueError,IndexError): meta['gps_checksum']='INVALID_EMBEDDED_GGA'
                break
            ensemble.append(meta)
            for row in rows:
                row.update(survey_date=date.isoformat(),source_file=raw,source_sha256=hashes[raw],ensemble_number=meta['ensemble_number'],
                    rtc_native_naive=meta['rtc_native_naive'],coordinate_system=meta['coordinate_system'],
                    velocity_frame='WATER_RELATIVE_TO_INSTRUMENT',bottom_difference_status='RESEARCH_DIAGNOSTIC_NOT_VALIDATED',
                    available_at_utc=PUBLISHED,ingested_at_utc=acquired)
                velocity.append(row)
        sr=ensemble[ens_start:];vr=velocity[vel_start:]
        good_nav=[r for r in nav_rows if not r['qc_flags']]
        closest=min(good_nav,key=lambda r:haversine(r['latitude'],r['longitude'],target['target_lat'],target['target_lon'])) if good_nav else None
        surveys.append({'survey_date':date.isoformat(),'nmea_sentence_counts':dict(native_counts),'rmc_rows':len(nav_rows),'rmc_rejected':dict(rejections),
          'rmc_flagged_rows':sum(bool(r['qc_flags']) for r in nav_rows),'pd0_ensembles':len(sr),'bin_rows':len(vr),
          'coordinate_systems':sorted({r['coordinate_system'] for r in sr}),'cells':sorted({r['bins'] for r in sr}),
          'firmware':sorted({r['firmware'] for r in sr}),'frequency_khz':sorted({r['frequency_khz'] for r in sr}),
          'first_bin_centers_m':sorted({r['first_bin_center_from_transducer_m'] for r in sr}),
          'cell_size_m':sorted({r['cell_size_m'] for r in sr}),'blanking_m':sorted({r['blanking_m'] for r in sr}),
          'configured_transducer_depth_m':config_depth,'native_transducer_depth_m':sorted({r['native_transducer_depth_setting_m'] for r in sr}),
          'gps_to_rtc_offset_seconds':summary_nums(times),'embedded_gga_external_rmc_matches_within_3s_30m':len(matching),
          'gps_utc_start':min((r['observed_at_utc'] for r in good_nav),default=None),'gps_utc_end':max((r['observed_at_utc'] for r in good_nav),default=None),
          'closest_rmc_to_point_clear_reference':({'distance_km':haversine(closest['latitude'],closest['longitude'],target['target_lat'],target['target_lon'])/1000,
             'latitude':closest['latitude'],'longitude':closest['longitude'],'observed_at_utc':closest['observed_at_utc']} if closest else None),
          'structurally_screened_bin_rows':sum(r['structural_screen_pass'] for r in vr),
          'bin_flags':dict(collections.Counter(flag for r in vr for flag in r['qc_flags'].split(';') if flag))})
    csv_gz(out/'navigation_rmc.csv.gz',nav);csv_gz(out/'ensembles.csv.gz',ensemble);csv_gz(out/'velocity_bins.csv.gz',velocity)
    info=json.loads((listing_dir/'griidc-download-info.json').read_text())['dataset']
    result={'schema_version':1,'dataset':DATASET,'doi':'10.7266/N7B85630','status':'LOCAL_RESEARCH_DECODED_NOT_VALIDATED_CURRENT',
      'archive':{'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes()),'zip_crc':'PASS','file_count':len(manifest),
       'uncompressed_bytes':sum(x['bytes'] for x in manifest),'all_individual_provider_names_and_sizes_match':True,
       'provider_archive_checksum':info['checksum'],'provider_archive_checksum_matches_download':info['checksum']==sha(archive.read_bytes()),
       'provider_archive_declared_bytes':info['fileSizeRaw'],'original_archive_endpoint':'HTTP_500; generated ZIP endpoint used'},
      'raw_files':manifest,'surveys':surveys,'counts':{'survey_days':len(surveys),'navigation_rmc_rows':len(nav),'pd0_ensembles':len(ensemble),'velocity_bin_rows':len(velocity),
       'structurally_screened_bin_rows':sum(r['structural_screen_pass'] for r in velocity),'validated_current_rows':0,'training_labels_created':0},
      'point_clear_reference':{'lat':target['target_lat'],'lon':target['target_lon'],'source':'model_data/ngofs2_point_clear_nowcast_manifest.json',
       'meaning':'existing model target only; geometric separation is not shore-normal-current validation'},
      'source_conflicts':['Provider calls this Nortek AWAC; native files are RDI PD0 plus WinRiver configuration.',
       'ADCP RTC timezone unresolved; GPS UTC does not establish RTC timezone.',
       'WinRiver transducer depth setting differs from native leader setting; actual deployment depth is unverified.',
       'Generated ZIP differs from provider original archive checksum; all 68 individual file names/sizes and ZIP CRC verify, original endpoint fails.'],
      'acceptance_limits':['Native SHIP components retained; no absolute Earth vector or shore-normal projection accepted.',
       'Water-minus-bottom vectors are algebraic diagnostics, without moving-bed, compass, mounting or motion validation.',
       'Structural and conservative depth/side-lobe screening is not final scientific QC.',
       'Publication available_at in 2016 is later than all 2010 observations; not valid as-of real-time 2010 forecast input.',
       'No co-located bottom oxygen, local shoreline control, event matching, predictive skill or production improvement established.'],
      'production_action':'NO_CHANGE','production_weight':0,
      'outputs':{p.name:sha(p.read_bytes()) for p in sorted(out.glob('*.csv.gz'))}}
    (out/'ingestion_summary.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps(result['counts']))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,required=True);p.add_argument('--listing-dir',type=pathlib.Path,required=True)
    p.add_argument('--repo',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True)
    a=p.parse_args();run(a.archive,a.listing_dir,a.repo,a.out)

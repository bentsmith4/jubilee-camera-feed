"""Owner-only shoreline burst. No R2/public Git uploads or vision API calls."""
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
import refresh_all as ra
import burst_capture as bc
from playwright.sync_api import sync_playwright

BASE=Path(r'C:\JubileeCams')
ROOT=BASE/'private_captures'

def main():
    ROOT.mkdir(exist_ok=True)
    state={'camera_id':'montrose_shoreline','media_publish_policy':'private_only',
           'checked_at':datetime.now(ra.TZ).isoformat(),'ok':False}
    try:
        token=ra.refresh_access_token(ra.load_credentials())
        matches=[d for d in ra.list_devices(token) if ra.custom_name(d).strip().casefold()=='looking at beach camera']
        if len(matches)!=1:
            state['error']='device_not_in_permitted_inventory' if not matches else 'ambiguous_device_name'
        else:
            device=matches[0]
            proto=ra.protocols(device)
            state['supportedProtocols']=proto
            capture_id=datetime.now(ra.TZ).strftime('%Y%m%dT%H%M%S%f')
            folder=ROOT/capture_id
            folder.mkdir()
            bc.BURST_DIR=folder
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True)
                try:
                    if 'WEB_RTC' in proto:
                        shots=bc.capture_webrtc_burst(browser,token,device,'montrose_shoreline')
                    elif 'RTSP' in proto:
                        shots=bc.capture_rtsp_burst(token,device,'montrose_shoreline')
                    else:raise ValueError('unsupported_protocol')
                finally:browser.close()
            state.update(ok=True,capture_id=capture_id,shots=shots,
                         sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.glob('*.jpg')},
                         roi_status='local_visual_calibration_pending')
            (folder/'manifest.json').write_text(json.dumps(state,indent=2))
    except Exception as exc:
        state['error']=type(exc).__name__
    temp=ROOT/'status.tmp'
    temp.write_text(json.dumps(state,indent=2))
    temp.replace(ROOT/'status.json')
    print('PRIVATE SHORELINE: '+('captured locally; public publication excluded' if state['ok'] else state['error']))
    return 0

if __name__=='__main__':sys.exit(main())

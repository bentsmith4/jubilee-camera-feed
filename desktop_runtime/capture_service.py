"""One bounded acquisition queue, distinct live and canonical products."""
import json,socket,subprocess,sys,time
from datetime import datetime,timedelta
from pathlib import Path
import refresh_all as ra

BASE=Path(r'C:\JubileeCams')
STATE=BASE/'capture_service_state.json'
LOG=BASE/'capture_service.log'

def slot(now,start,end):
    if start<=now<=end:
        return 'dawn:'+start.date().isoformat()+':'+str(int((now-start).total_seconds()//1200))
    hour=now.replace(minute=6,second=0,microsecond=0)
    if now<hour:hour-=timedelta(hours=1)
    return 'hour:'+hour.isoformat()

def log(message):
    with LOG.open('a',encoding='utf-8') as out:out.write(datetime.now(ra.TZ).isoformat()+' '+message+'\n')

def execute(script,limit):
    process=subprocess.Popen([sys.executable,str(BASE/script)],cwd=BASE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        stdout,_stderr=process.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
        process.communicate()
        log(script+' timeout; child process tree stopped')
        return False
    # Log only allowlisted completion summaries, not child exceptions or URLs.
    for line in stdout.splitlines():
        if line.startswith(('GITHUB APPEND-ONLY PUBLISH SUCCESS:', 'PRIVATE SHORELINE:', 'FULL JUBILEE BURST', 'Fresh cameras published:')):
            log(line)
    log(script+' exit='+str(process.returncode))
    return process.returncode==0

def main():
    lock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:lock.bind(('127.0.0.1',47651))
    except OSError:return
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    next_live=0
    retry_at=0
    failures=0
    log('Coordinated capture service started')
    while True:
        now,_dawn,start,end=ra.dawn_window()
        due=slot(now,start,end)
        if state.get('canonical_slot')!=due and time.monotonic()>=retry_at:
            if execute('capture_publish.py',900):
                state['canonical_slot']=due
                state['last_canonical_success']=datetime.now(ra.TZ).isoformat()
                failures=0
            else:
                failures+=1
                retry_at=time.monotonic()+min(900,60*2**min(failures,4))
                state['canonical_failures']=failures
                log('Canonical failure; bounded backoff applied')
        if time.monotonic()>=next_live:
            if execute('live_capture.py',300):
                if execute('live_upload.py',90):state['last_live_success']=datetime.now(ra.TZ).isoformat()
            next_live=time.monotonic()+180
        state['heartbeat']=datetime.now(ra.TZ).isoformat()
        tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2));tmp.replace(STATE)
        time.sleep(5)

if __name__=='__main__':main()

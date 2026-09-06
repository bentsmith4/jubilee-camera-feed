"""Capture validation, immutable local snapshots, and verified R2 writes."""
import hashlib
import io
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image

from camera_policy import CAMERA_IDS
PUBLIC_CAMERAS = set(CAMERA_IDS)

def freeze(base):
    frames=base/'frames'
    docs={n:json.loads((frames/n).read_text(encoding='utf-8-sig')) for n in ['status.json','vision.json','burst_status.json']}
    status=docs['status.json']
    capture=status['capture_time_ct']
    dt=datetime.fromisoformat(capture)
    if dt.tzinfo is None or not -timedelta(minutes=2)<=datetime.now(timezone.utc)-dt<=timedelta(hours=1):
        raise ValueError('Invalid capture time')
    blobs={}
    for name,doc in docs.items():
        if doc.get('capture_time_ct')!=capture:raise ValueError('Capture schema mismatch')
        if set(doc.get('cameras',{}))-PUBLIC_CAMERAS:raise ValueError('Private camera excluded from public archive')
        blobs[name]=(frames/name).read_bytes()
    for camera, info in status['cameras'].items():
        if not info.get('ok'):continue
        shots=docs['burst_status.json']['cameras'].get(camera,{}).get('shots',[])
        if len(shots)!=3 or {s['shot'] for s in shots}!={1,2,3}:raise ValueError('Incomplete burst')
        for name in [camera+'.jpg']+['burst_latest/'+camera+'_'+str(s['shot'])+'.jpg' for s in shots]:
            content=(frames/name).read_bytes()
            Image.open(io.BytesIO(content)).verify()
            blobs[name]=content
    digest=hashlib.sha256(b''.join(k.encode()+v for k,v in sorted(blobs.items()))).hexdigest()
    capture_id=dt.strftime('%Y%m%dT%H%M%S%f')+'-'+digest[:12]
    target=base/'captures'/capture_id
    target.mkdir(parents=True,exist_ok=True)
    hashes={name:hashlib.sha256(content).hexdigest() for name,content in blobs.items()}
    for name,content in blobs.items():
        dest=target/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if dest.read_bytes()!=content:raise ValueError('Immutable capture conflict')
        else:
            with dest.open('xb') as out:out.write(content)
    metadata={'capture_id':capture_id,'capture_time_ct':capture,'sha256':hashes}
    seal=target/'capture_manifest.json'
    encoded=json.dumps(metadata,indent=2).encode()
    if not seal.exists():
        with seal.open('xb') as out:out.write(encoded)
    elif seal.read_bytes()!=encoded:raise ValueError('Immutable manifest conflict')
    return target,metadata

class VerifiedStore:
    def __init__(self,client):
        self.client=client
        self.hashes={}
    def verify(self,bucket,key,content):
        actual=self.client.get_object(Bucket=bucket,Key=key)['Body'].read()
        digest=hashlib.sha256(content).hexdigest()
        if hashlib.sha256(actual).hexdigest()!=digest:raise ValueError('R2 verification failed')
        self.hashes[key]=digest
    def upload_file(self,filename,bucket,key,**kwargs):
        content=Path(filename).read_bytes()
        self.client.upload_file(filename,bucket,key,**kwargs)
        self.verify(bucket,key,content)
    def put_object(self,**kwargs):
        body=kwargs['Body']
        self.client.put_object(**kwargs)
        self.verify(kwargs['Bucket'],kwargs['Key'],body)

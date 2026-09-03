"""Vector 5250 backup replication and Data Relay telemetry.

Vector remains an independent system of record. This module mirrors durable
Vector records/journal rows into the independent backup service and sends
operational health/change telemetry to the Data Relay Server.
"""
import hashlib, json, os, sqlite3, threading, time, urllib.request
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from auth import require_permission, is_master

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'vector5250.db')
BACKUP_URL=os.environ.get('BACKUP_SERVICE_URL','https://uga-backup-service-production.up.railway.app').rstrip('/')
BACKUP_TOKEN=os.environ.get('BACKUP_SYNC_TOKEN','').strip()
DRS_URL=os.environ.get('DRS_URL','').rstrip('/')
DRS_SERVICE_ID=os.environ.get('DRS_VECTOR_SERVICE_ID',os.environ.get('DRS_SERVICE_ID','vector5250'))
DRS_SERVICE_KEY=os.environ.get('DRS_VECTOR_SERVICE_KEY',os.environ.get('DRS_SERVICE_KEY',''))
POLL=max(15,int(os.environ.get('VECTOR_REPLICATION_SECONDS','15')))
PERM='warehouse:manager'
router=APIRouter(tags=['Vector 5250 Resilience'])
_lock=threading.Lock();_started=False;_last_digest=None
_state={'running':False,'last_check':None,'last_change':None,'backup_last_success':None,'backup_last_error':None,'relay_last_success':None,'relay_last_error':None,'records':0,'journal':0}

def _now(): return datetime.now(timezone.utc).isoformat()
def _auth(code):
    if is_master(code): return
    try: require_permission(code,PERM)
    except HTTPException: raise HTTPException(status_code=403,detail='Vector 5250 manager access required')
def _read():
    if not os.path.exists(DB): return [],[]
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    try:
        records=[dict(r) for r in c.execute('SELECT * FROM vector_records ORDER BY record_no').fetchall()]
        journal=[dict(r) for r in c.execute('SELECT * FROM vector_journal ORDER BY created_at').fetchall()]
        return records,journal
    finally:c.close()
def _digest(records,journal):
    return hashlib.sha256(json.dumps({'records':records,'journal':journal},sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def _post(url,payload,headers,timeout=8):
    req=urllib.request.Request(url,data=json.dumps(payload,default=str).encode(),method='POST',headers={'Content-Type':'application/json',**headers})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        r.read()
        if not 200<=r.status<300: raise RuntimeError(f'HTTP {r.status}')
def _backup(records,journal):
    if not BACKUP_TOKEN:
        _state['backup_last_error']='BACKUP_SYNC_TOKEN not configured';return False
    try:
        for entity_type,rows in [('vector_record',records),('vector_journal',journal)]:
            for i in range(0,len(rows),500):
                _post(BACKUP_URL+'/sync/bulk',{'source':'VECTOR5250','entity_type':entity_type,'records':rows[i:i+500]},{'x-backup-token':BACKUP_TOKEN},30)
        _state['backup_last_success']=_now();_state['backup_last_error']=None;return True
    except Exception as exc:
        _state['backup_last_error']=f'{type(exc).__name__}: {exc}'[:240];return False
def _relay(category,payload):
    if not (DRS_URL and DRS_SERVICE_KEY):
        _state['relay_last_error']='DRS_URL/DRS service key not configured';return False
    event={'category':category,'severity':'info','source':'vector5250','timestamp':time.time(),'payload':payload}
    try:
        _post(DRS_URL+'/events',event,{'X-Service-ID':DRS_SERVICE_ID,'X-Service-Key':DRS_SERVICE_KEY},4)
        _state['relay_last_success']=_now();_state['relay_last_error']=None;return True
    except Exception as exc:
        _state['relay_last_error']=f'{type(exc).__name__}: {exc}'[:240];return False

def replicate_once(force=False):
    global _last_digest
    records,journal=_read();digest=_digest(records,journal);changed=force or digest!=_last_digest
    _state['last_check']=_now();_state['records']=len(records);_state['journal']=len(journal)
    if changed:
        _state['last_change']=_now();_backup(records,journal);_relay('vector5250.replication',{'records':len(records),'journal':len(journal),'digest':digest[:16]});_last_digest=digest
    elif int(time.time())%60 < POLL:
        _relay('vector5250.heartbeat',{'records':len(records),'journal':len(journal),'backup_last_success':_state['backup_last_success']})
    return dict(_state)
def _worker():
    _state['running']=True
    while True:
        try: replicate_once()
        except Exception as exc:
            _state['backup_last_error']=f'worker: {type(exc).__name__}: {exc}'[:240]
        time.sleep(POLL)
def start():
    global _started
    with _lock:
        if _started:return
        _started=True;threading.Thread(target=_worker,name='vector5250-resilience',daemon=True).start()
start()

@router.get('/vector5250/api/resilience')
def resilience_status(x_access_code:str=Header(default='')):
    _auth(x_access_code)
    return {**dict(_state),'backup_configured':bool(BACKUP_TOKEN),'backup_service':BACKUP_URL,'relay_configured':bool(DRS_URL and DRS_SERVICE_KEY),'relay_service_id':DRS_SERVICE_ID,'poll_seconds':POLL}

@router.post('/vector5250/api/resilience/sync')
def resilience_sync(x_access_code:str=Header(default='')):
    _auth(x_access_code);return replicate_once(force=True)

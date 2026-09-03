"""Vector 5250 execution worker for submitted and scheduled jobs."""
import sqlite3, threading, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from auth import require_permission, is_master
from vector5250_resilience import replicate_once

DB=Path('vector5250.db');PERM='warehouse:manager';POLL=10
router=APIRouter(prefix='/vector5250',tags=['Vector 5250 Execution'])
_state={'running':False,'last_cycle':None,'last_job':None,'last_error':None,'completed':0,'failed':0}
_started=False;_lock=threading.Lock()

def auth(code):
    if not is_master(code):require_permission(code,PERM)
def con():
    c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE IF NOT EXISTS vector_submitted_jobs(id TEXT PRIMARY KEY,job_name TEXT,command TEXT,job_queue TEXT,status TEXT,submitted_by TEXT,submitted_at TEXT,started_at TEXT,completed_at TEXT);CREATE TABLE IF NOT EXISTS vector_job_schedule(id TEXT PRIMARY KEY,entry_name TEXT,command TEXT,frequency TEXT,next_run TEXT,status TEXT,created_by TEXT,created_at TEXT,last_run TEXT);CREATE TABLE IF NOT EXISTS vector_spool(id TEXT PRIMARY KEY,spool_no INTEGER UNIQUE NOT NULL,file_name TEXT NOT NULL,user_id TEXT NOT NULL,job_name TEXT NOT NULL,outq TEXT NOT NULL,status TEXT NOT NULL,pages INTEGER NOT NULL DEFAULT 1,copies INTEGER NOT NULL DEFAULT 1,form_type TEXT NOT NULL DEFAULT 'STD',content TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,updated_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS vector_messages(message_id TEXT PRIMARY KEY,queue_name TEXT NOT NULL,severity INTEGER NOT NULL DEFAULT 0,message_type TEXT NOT NULL DEFAULT 'INFO',status TEXT NOT NULL DEFAULT 'NEW',sender TEXT NOT NULL,text TEXT NOT NULL,reply_text TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,replied_at REAL);''')
    cols={r['name'] for r in c.execute('PRAGMA table_info(vector_submitted_jobs)')}
    if 'result_text' not in cols:c.execute('ALTER TABLE vector_submitted_jobs ADD COLUMN result_text TEXT')
    if 'attempts' not in cols:c.execute('ALTER TABLE vector_submitted_jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0')
    c.commit();return c

def iso_now():return datetime.now(timezone.utc).isoformat()
def parse_dt(s):
    if not s:return None
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:
        try:return datetime.strptime(str(s),'%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        except Exception:return None

def next_time(base,frequency):
    f=(frequency or '').upper()
    if f in {'ONCE','ONE-TIME','ONETIME'}:return None
    if f=='HOURLY':return base+timedelta(hours=1)
    if f=='WEEKLY':return base+timedelta(days=7)
    return base+timedelta(days=1)

def spool(c,user,job,text,outq='QREPORT'):
    n=c.execute('SELECT COALESCE(MAX(spool_no),0)+1 n FROM vector_spool').fetchone()['n'];now=time.time();c.execute('INSERT INTO vector_spool VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,int(n),'VECTORJOB',user,job,outq,'READY',1,1,'STD',text,now,now))

def execute(c,row):
    cmd=(row['command'] or '').strip();upper=cmd.upper();user=(row['submitted_by'] or 'VECTOR').upper();job=(row['job_name'] or row['id']).upper()
    if upper.startswith('REPORT'):
        parts=upper.split(maxsplit=1);rtype=parts[1].strip() if len(parts)>1 else ''
        sql='SELECT record_no,record_type,status,title,location,owner FROM vector_records';args=[]
        if rtype:sql+=' WHERE record_type=?';args=[rtype]
        sql+=' ORDER BY updated_at DESC LIMIT 200'
        try:rows=c.execute(sql,args).fetchall()
        except sqlite3.OperationalError:rows=[]
        lines=[f'VECTOR 5250 REPORT {rtype or "ALL RECORDS"}',f'GENERATED {iso_now()}', '']+[f"{r['record_no']} | {r['record_type']} | {r['status']} | {r['title']}" for r in rows]
        result='\n'.join(lines);spool(c,user,job,result);return result
    if upper in {'SYNC','SYNC BACKUP','BACKUP SYNC','FORCE SYNC'}:
        st=replicate_once(force=True);result=f"BACKUP/RELAY SYNC REQUESTED. RECORDS={st.get('records',0)} JOURNAL={st.get('journal',0)}";spool(c,user,job,result,'QAUDIT');return result
    if upper.startswith('MESSAGE '):
        text=cmd[8:].strip();mid='MSG'+uuid.uuid4().hex[:9].upper();c.execute('INSERT INTO vector_messages(message_id,queue_name,severity,message_type,status,sender,text,created_at) VALUES(?,?,?,?,?,?,?,?)',(mid,'QSYSOPR',20,'BATCH','NEW',user,text,time.time()));result=f'MESSAGE {mid} SENT TO QSYSOPR';spool(c,user,job,result,'QAUDIT');return result
    raise ValueError('Unsupported batch command. Use REPORT [TYPE], SYNC BACKUP, or MESSAGE <text>.')

def enqueue_due(c):
    now=datetime.now(timezone.utc)
    rows=c.execute("SELECT * FROM vector_job_schedule WHERE status='ACTIVE' AND next_run IS NOT NULL AND next_run!=''").fetchall()
    for r in rows:
        due=parse_dt(r['next_run'])
        if not due or due>now:continue
        jid=uuid.uuid4().hex[:10].upper();job=(r['entry_name'] or 'SCHEDULE')[:20].upper();c.execute('INSERT INTO vector_submitted_jobs(id,job_name,command,job_queue,status,submitted_by,submitted_at,started_at,completed_at,result_text,attempts) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,job,r['command'],'QBATCH','QUEUED',r['created_by'] or 'VECTOR',iso_now(),None,None,None,0));nxt=next_time(due,r['frequency']);c.execute('UPDATE vector_job_schedule SET last_run=?,next_run=?,status=? WHERE id=?',(iso_now(),nxt.isoformat() if nxt else None,'ACTIVE' if nxt else 'COMPLETED',r['id']))

def cycle():
    c=con()
    try:
        enqueue_due(c);c.commit();rows=c.execute("SELECT * FROM vector_submitted_jobs WHERE status='QUEUED' ORDER BY submitted_at LIMIT 5").fetchall()
        for r in rows:
            c.execute("UPDATE vector_submitted_jobs SET status='RUNNING',started_at=?,attempts=COALESCE(attempts,0)+1 WHERE id=?",(iso_now(),r['id']));c.commit()
            try:
                result=execute(c,r);c.execute("UPDATE vector_submitted_jobs SET status='COMPLETED',completed_at=?,result_text=? WHERE id=?",(iso_now(),result[:4000],r['id']));_state['completed']+=1;_state['last_error']=None
            except Exception as exc:
                err=f'{type(exc).__name__}: {exc}';c.execute("UPDATE vector_submitted_jobs SET status='FAILED',completed_at=?,result_text=? WHERE id=?",(iso_now(),err[:4000],r['id']));spool(c,(r['submitted_by'] or 'VECTOR').upper(),(r['job_name'] or r['id']).upper(),err,'QAUDIT');_state['failed']+=1;_state['last_error']=err[:240]
            c.commit();_state['last_job']=r['job_name']
        _state['last_cycle']=iso_now()
    finally:c.close()

def worker():
    _state['running']=True
    while True:
        try:cycle()
        except Exception as exc:_state['last_error']=f'worker: {type(exc).__name__}: {exc}'[:240]
        time.sleep(POLL)
def start():
    global _started
    with _lock:
        if _started:return
        _started=True;threading.Thread(target=worker,name='vector5250-executor',daemon=True).start()
start()

@router.get('/execution/status')
def status(x_access_code:str=Header(default='')):
    auth(x_access_code);return {**_state,'poll_seconds':POLL}
@router.post('/execution/run-once')
def run_once(x_access_code:str=Header(default='')):
    auth(x_access_code);cycle();return {**_state,'poll_seconds':POLL}

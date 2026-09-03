"""Vector 5250 active-job and subsystem monitor.

Provides IBM i-inspired WRKACTJOB / WRKSBS views for the independent Vector host.
Interactive sessions are heartbeated by the 5250 client and expire automatically.
System jobs are derived from live Vector worker threads, not Warehouse processes.
"""
import os, sqlite3, threading, time, uuid
from fastapi import APIRouter, Header, HTTPException, Body
from auth import require_permission, is_master

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'vector5250.db')
PERM='warehouse:manager'
SESSION_TTL=max(60,int(os.environ.get('VECTOR_SESSION_TTL_SECONDS','90')))
router=APIRouter(tags=['Vector 5250 Jobs'])

def _auth(code:str):
    if is_master(code): return
    try: require_permission(code,PERM)
    except HTTPException: raise HTTPException(status_code=403,detail='Vector 5250 manager access required')

def _db():
    c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c

def _init():
    c=_db()
    c.execute('''CREATE TABLE IF NOT EXISTS vector_sessions(
        session_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,role TEXT NOT NULL DEFAULT '',
        subsystem TEXT NOT NULL DEFAULT 'QINTER',screen_id TEXT NOT NULL DEFAULT 'MAIN',
        client_id TEXT NOT NULL DEFAULT '',started_at REAL NOT NULL,last_seen REAL NOT NULL,
        signed_off_at REAL
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vector_sessions_seen ON vector_sessions(last_seen,signed_off_at)')
    c.close()
_init()

def _clean(c):
    cutoff=time.time()-SESSION_TTL
    c.execute("UPDATE vector_sessions SET signed_off_at=COALESCE(signed_off_at,last_seen) WHERE signed_off_at IS NULL AND last_seen<?",(cutoff,))

def _session_job(row):
    now=time.time();age=max(0,int(now-row['last_seen']))
    return {
        'job_name':f"V{row['session_id'][:8].upper()}",
        'user':row['user_id'],'type':'INTERACTIVE','subsystem':row['subsystem'],
        'status':'RUN' if row['signed_off_at'] is None and age<=SESSION_TTL else 'OUTQ',
        'function':row['screen_id'],'elapsed_seconds':max(0,int(now-row['started_at'])),
        'idle_seconds':age,'session_id':row['session_id'],'client_id':row['client_id']
    }

def _system_jobs():
    names={t.name for t in threading.enumerate() if t.is_alive()}
    specs=[
        ('V5250HOST','QVECTOR','HOST SERVER','MainThread'),
        ('V5250REPL','QSYSWRK','BACKUP / RELAY REPLICATION','vector5250-resilience'),
        ('V5250BKRCL','QSYSWRK','BACKUP RECONCILIATION','uga-backup-reconcile'),
    ]
    rows=[]
    for job,sbs,func,thread_name in specs:
        active=(thread_name in names) or (thread_name=='MainThread' and 'MainThread' in names)
        rows.append({'job_name':job,'user':'QSYS','type':'SYSTEM','subsystem':sbs,'status':'RUN' if active else 'END','function':func,'elapsed_seconds':None,'idle_seconds':0,'thread':thread_name})
    return rows

@router.post('/vector5250/api/jobs/session')
def start_or_heartbeat(payload:dict=Body(default={}),x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);now=time.time();sid=str(payload.get('session_id') or '').strip() or uuid.uuid4().hex
    role=str(payload.get('role') or '').upper();screen=str(payload.get('screen_id') or 'MAIN').upper()[:16];client=str(payload.get('client_id') or '')[:80]
    c=_db();_clean(c);existing=c.execute('SELECT session_id FROM vector_sessions WHERE session_id=?',(sid,)).fetchone()
    if existing:
        c.execute('UPDATE vector_sessions SET user_id=?,role=?,screen_id=?,client_id=?,last_seen=?,signed_off_at=NULL WHERE session_id=?',(x_vector_user,role,screen,client,now,sid))
    else:
        c.execute('INSERT INTO vector_sessions(session_id,user_id,role,screen_id,client_id,started_at,last_seen) VALUES(?,?,?,?,?,?,?)',(sid,x_vector_user,role,screen,client,now,now))
    c.close();return {'session_id':sid,'heartbeat_seconds':20,'expires_after_seconds':SESSION_TTL}

@router.delete('/vector5250/api/jobs/session/{session_id}')
def end_session(session_id:str,x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);c=_db();row=c.execute('SELECT * FROM vector_sessions WHERE session_id=?',(session_id,)).fetchone()
    if row and row['user_id']!=x_vector_user and not is_master(x_access_code):c.close();raise HTTPException(403,'Cannot end another Vector session')
    c.execute('UPDATE vector_sessions SET signed_off_at=?,last_seen=? WHERE session_id=?',(time.time(),time.time(),session_id));c.close();return {'session_id':session_id,'ended':True}

@router.get('/vector5250/api/jobs')
def active_jobs(x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();_clean(c);rows=[_session_job(r) for r in c.execute('SELECT * FROM vector_sessions WHERE signed_off_at IS NULL ORDER BY started_at').fetchall()];c.close()
    jobs=_system_jobs()+rows
    return {'count':len(jobs),'active_interactive':len(rows),'jobs':jobs,'checked_at':time.time()}

@router.get('/vector5250/api/subsystems')
def subsystems(x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();_clean(c);interactive=c.execute("SELECT COUNT(*) n FROM vector_sessions WHERE signed_off_at IS NULL AND subsystem='QINTER'").fetchone()['n'];c.close()
    system=_system_jobs();syswrk=sum(1 for j in system if j['subsystem']=='QSYSWRK' and j['status']=='RUN')
    rows=[
        {'subsystem':'QVECTOR','status':'ACTIVE','active_jobs':1,'max_jobs':64,'description':'VECTOR 5250 HOST'},
        {'subsystem':'QINTER','status':'ACTIVE','active_jobs':interactive,'max_jobs':250,'description':'INTERACTIVE VECTOR SESSIONS'},
        {'subsystem':'QSYSWRK','status':'ACTIVE','active_jobs':syswrk,'max_jobs':64,'description':'VECTOR SYSTEM WORKERS'},
        {'subsystem':'QBATCH','status':'ACTIVE','active_jobs':0,'max_jobs':32,'description':'VECTOR BATCH WORK'},
    ]
    return {'count':len(rows),'subsystems':rows,'checked_at':time.time()}

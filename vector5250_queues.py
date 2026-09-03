"""Vector 5250 job queues, output queues, and spooled files."""
import os, sqlite3, time, uuid
from fastapi import APIRouter, Header, HTTPException, Body, Query
from auth import require_permission, is_master

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'vector5250.db')
PERM='warehouse:manager'
router=APIRouter(tags=['Vector 5250 Queues'])

def _auth(code:str):
    if is_master(code): return
    try: require_permission(code,PERM)
    except HTTPException: raise HTTPException(status_code=403,detail='Vector 5250 manager access required')

def _db():
    c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c

def _init():
    c=_db();c.execute('BEGIN IMMEDIATE')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_jobq(id TEXT PRIMARY KEY,job_name TEXT UNIQUE NOT NULL,queue_name TEXT NOT NULL,user_id TEXT NOT NULL,status TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 50,function TEXT NOT NULL DEFAULT '',submitted_at REAL NOT NULL,started_at REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vector_spool(id TEXT PRIMARY KEY,spool_no INTEGER UNIQUE NOT NULL,file_name TEXT NOT NULL,user_id TEXT NOT NULL,job_name TEXT NOT NULL,outq TEXT NOT NULL,status TEXT NOT NULL,pages INTEGER NOT NULL DEFAULT 1,copies INTEGER NOT NULL DEFAULT 1,form_type TEXT NOT NULL DEFAULT 'STD',content TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vjobq_queue ON vector_jobq(queue_name,status,priority,submitted_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_vspool_outq ON vector_spool(outq,status,created_at)')
    c.execute('COMMIT');c.close()
_init()

def _next_spool(c):
    r=c.execute('SELECT COALESCE(MAX(spool_no),0)+1 n FROM vector_spool').fetchone();return int(r['n'])

@router.get('/vector5250/api/job-queues')
def job_queues(x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();rows=[dict(r) for r in c.execute('SELECT queue_name,status,COUNT(*) queued,MIN(priority) top_priority FROM vector_jobq GROUP BY queue_name,status ORDER BY queue_name,status').fetchall()];c.close()
    defaults=['QBATCH','QREPORT','QSYNC','QDOCUMENT']
    out=[]
    for q in defaults:
        qs=[r for r in rows if r['queue_name']==q];out.append({'queue_name':q,'status':'RELEASED','queued':sum(r['queued'] for r in qs if r['status']=='QUEUED'),'held':sum(r['queued'] for r in qs if r['status']=='HELD'),'top_priority':min([r['top_priority'] for r in qs if r['top_priority'] is not None],default=None)})
    return {'count':len(out),'queues':out}

@router.get('/vector5250/api/job-queues/{queue_name}')
def queue_jobs(queue_name:str,x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();rows=[dict(r) for r in c.execute('SELECT * FROM vector_jobq WHERE queue_name=? ORDER BY CASE status WHEN "QUEUED" THEN 0 WHEN "HELD" THEN 1 ELSE 2 END,priority,submitted_at',(queue_name.upper(),)).fetchall()];c.close();return {'queue_name':queue_name.upper(),'count':len(rows),'jobs':rows}

@router.post('/vector5250/api/job-queues/{queue_name}/submit')
def submit_job(queue_name:str,payload:dict=Body(...),x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);name=str(payload.get('job_name') or f'JOB{uuid.uuid4().hex[:8].upper()}').upper();priority=max(1,min(99,int(payload.get('priority',50))));fn=str(payload.get('function') or 'VECTOR BATCH WORK').upper();now=time.time();c=_db();c.execute('BEGIN IMMEDIATE')
    try:
        c.execute('INSERT INTO vector_jobq VALUES(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),name,queue_name.upper(),x_vector_user.upper(),'QUEUED',priority,fn,now,None));c.execute('COMMIT');return {'job_name':name,'queue_name':queue_name.upper(),'status':'QUEUED','priority':priority}
    except sqlite3.IntegrityError:c.execute('ROLLBACK');raise HTTPException(409,'Job already exists')
    finally:c.close()

@router.post('/vector5250/api/job-queues/job/{job_name}/action')
def job_action(job_name:str,payload:dict=Body(...),x_access_code:str=Header(default='')):
    _auth(x_access_code);action=str(payload.get('action') or '').upper();c=_db();c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM vector_jobq WHERE job_name=?',(job_name.upper(),)).fetchone()
    if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Queued job not found')
    if action=='HOLD':status='HELD'
    elif action=='RELEASE':status='QUEUED'
    elif action=='RUN':status='RUNNING'
    elif action=='CANCEL':status='CANCELLED'
    else:c.execute('ROLLBACK');c.close();raise HTTPException(400,'Action must be HOLD, RELEASE, RUN, or CANCEL')
    c.execute('UPDATE vector_jobq SET status=?,started_at=CASE WHEN ?="RUNNING" THEN ? ELSE started_at END WHERE job_name=?',(status,status,time.time(),job_name.upper()));c.execute('COMMIT');out=dict(c.execute('SELECT * FROM vector_jobq WHERE job_name=?',(job_name.upper(),)).fetchone());c.close();return out

@router.get('/vector5250/api/output-queues')
def output_queues(x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();rows=[dict(r) for r in c.execute('SELECT outq,status,COUNT(*) files,COALESCE(SUM(pages),0) pages FROM vector_spool GROUP BY outq,status').fetchall()];c.close();defaults=['QPRINT','QREPORT','QDOCOUT','QAUDIT'];out=[]
    for q in defaults:
        qs=[r for r in rows if r['outq']==q];out.append({'outq':q,'status':'RELEASED','files':sum(r['files'] for r in qs),'pages':sum(r['pages'] for r in qs),'held':sum(r['files'] for r in qs if r['status']=='HELD')})
    return {'count':len(out),'queues':out}

@router.get('/vector5250/api/spooled-files')
def spooled_files(outq:str=Query(''),user:str=Query(''),x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();sql='SELECT * FROM vector_spool WHERE 1=1';a=[]
    if outq:sql+=' AND outq=?';a.append(outq.upper())
    if user:sql+=' AND user_id=?';a.append(user.upper())
    sql+=' ORDER BY created_at DESC';rows=[dict(r) for r in c.execute(sql,a).fetchall()];c.close();return {'count':len(rows),'files':rows}

@router.post('/vector5250/api/spooled-files')
def create_spool(payload:dict=Body(...),x_access_code:str=Header(default=''),x_vector_user:str=Header(default='SYSTEM')):
    _auth(x_access_code);c=_db();c.execute('BEGIN IMMEDIATE');now=time.time();no=_next_spool(c);file_name=str(payload.get('file_name') or 'VECTORRPT').upper();job_name=str(payload.get('job_name') or 'INTERACTIVE').upper();outq=str(payload.get('outq') or 'QREPORT').upper();pages=max(1,int(payload.get('pages',1)));content=str(payload.get('content') or '')
    c.execute('INSERT INTO vector_spool VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),no,file_name,x_vector_user.upper(),job_name,outq,'READY',pages,1,str(payload.get('form_type') or 'STD').upper(),content,now,now));c.execute('COMMIT');row=dict(c.execute('SELECT * FROM vector_spool WHERE spool_no=?',(no,)).fetchone());c.close();return row

@router.get('/vector5250/api/spooled-files/{spool_no}')
def get_spool(spool_no:int,x_access_code:str=Header(default='')):
    _auth(x_access_code);c=_db();r=c.execute('SELECT * FROM vector_spool WHERE spool_no=?',(spool_no,)).fetchone();c.close()
    if not r:raise HTTPException(404,'Spooled file not found')
    return dict(r)

@router.post('/vector5250/api/spooled-files/{spool_no}/action')
def spool_action(spool_no:int,payload:dict=Body(...),x_access_code:str=Header(default='')):
    _auth(x_access_code);action=str(payload.get('action') or '').upper();c=_db();c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM vector_spool WHERE spool_no=?',(spool_no,)).fetchone()
    if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Spooled file not found')
    mapping={'HOLD':'HELD','RELEASE':'READY','PRINT':'PRINTED','DELETE':'DELETED'}
    if action not in mapping:c.execute('ROLLBACK');c.close();raise HTTPException(400,'Action must be HOLD, RELEASE, PRINT, or DELETE')
    c.execute('UPDATE vector_spool SET status=?,updated_at=? WHERE spool_no=?',(mapping[action],time.time(),spool_no));c.execute('COMMIT');out=dict(c.execute('SELECT * FROM vector_spool WHERE spool_no=?',(spool_no,)).fetchone());c.close();return out

"""Vector 5250 submitted jobs and scheduled job entries."""
import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from auth import require_permission, is_master

router=APIRouter(prefix="/vector5250", tags=["Vector 5250 Scheduler"])
DB=Path("vector5250.db")
PERM="warehouse:manager"

def auth(code):
    if not is_master(code): require_permission(code,PERM)
def now(): return datetime.now(timezone.utc).isoformat()
def con():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE IF NOT EXISTS vector_submitted_jobs(id TEXT PRIMARY KEY,job_name TEXT,command TEXT,job_queue TEXT,status TEXT,submitted_by TEXT,submitted_at TEXT,started_at TEXT,completed_at TEXT);CREATE TABLE IF NOT EXISTS vector_job_schedule(id TEXT PRIMARY KEY,entry_name TEXT,command TEXT,frequency TEXT,next_run TEXT,status TEXT,created_by TEXT,created_at TEXT,last_run TEXT);'''); c.commit(); return c
class Submit(BaseModel):
    job_name:str; command:str; job_queue:str="QBATCH"; user:str="VECTOR"
class Schedule(BaseModel):
    entry_name:str; command:str; frequency:str="DAILY"; next_run:str=""; user:str="VECTOR"
@router.get("/submitted-jobs")
def jobs(x_access_code:str=Header(default="")):
    auth(x_access_code); c=con(); rows=[dict(r) for r in c.execute("SELECT * FROM vector_submitted_jobs ORDER BY submitted_at DESC LIMIT 100")]; c.close(); return {"jobs":rows}
@router.post("/submitted-jobs")
def submit(b:Submit,x_access_code:str=Header(default="")):
    auth(x_access_code); jid=uuid.uuid4().hex[:10].upper(); c=con(); c.execute("INSERT INTO vector_submitted_jobs VALUES(?,?,?,?,?,?,?,?,?)",(jid,b.job_name.upper()[:20],b.command[:500],b.job_queue.upper()[:20],"QUEUED",b.user.upper()[:20],now(),None,None)); c.commit(); c.close(); return {"id":jid,"status":"QUEUED"}
@router.post("/submitted-jobs/{jid}/{action}")
def job_action(jid:str,action:str,x_access_code:str=Header(default="")):
    auth(x_access_code); states={"hold":"HELD","release":"QUEUED","cancel":"CANCELLED"};
    if action not in states: raise HTTPException(400,"Invalid job action")
    c=con(); c.execute("UPDATE vector_submitted_jobs SET status=? WHERE id=?",(states[action],jid)); c.commit(); c.close(); return {"id":jid,"status":states[action]}
@router.get("/job-schedule")
def schedule(x_access_code:str=Header(default="")):
    auth(x_access_code); c=con(); rows=[dict(r) for r in c.execute("SELECT * FROM vector_job_schedule ORDER BY entry_name")]; c.close(); return {"entries":rows}
@router.post("/job-schedule")
def add_schedule(b:Schedule,x_access_code:str=Header(default="")):
    auth(x_access_code); sid=uuid.uuid4().hex[:10].upper(); c=con(); c.execute("INSERT INTO vector_job_schedule VALUES(?,?,?,?,?,?,?,?,?)",(sid,b.entry_name.upper()[:20],b.command[:500],b.frequency.upper()[:20],b.next_run or None,"ACTIVE",b.user.upper()[:20],now(),None)); c.commit(); c.close(); return {"id":sid,"status":"ACTIVE"}
@router.post("/job-schedule/{sid}/{action}")
def schedule_action(sid:str,action:str,x_access_code:str=Header(default="")):
    auth(x_access_code); states={"hold":"HELD","release":"ACTIVE","remove":"REMOVED"};
    if action not in states: raise HTTPException(400,"Invalid schedule action")
    c=con(); c.execute("UPDATE vector_job_schedule SET status=? WHERE id=?",(states[action],sid)); c.commit(); c.close(); return {"id":sid,"status":states[action]}

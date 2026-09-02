"""Explicit audit trail for the Data Relay Server: who did what, when, and how."""
import json, os, sqlite3, time, uuid
from typing import Any, Dict
from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field
from auth import require_permission

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('DATA_RELAY_DB',os.path.join(BASE,'data_hub.db'))
router=APIRouter(prefix='/platform/data-relay/audit',tags=['platform-data-relay-audit'])

def conn():
    c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c

def init():
    c=conn(); c.executescript('''
    CREATE TABLE IF NOT EXISTS data_relay_audit(
      id TEXT PRIMARY KEY,
      who TEXT NOT NULL,
      what TEXT NOT NULL,
      resource TEXT,
      result TEXT,
      how_method TEXT,
      how_channel TEXT,
      ip_address TEXT,
      user_agent TEXT,
      device_id TEXT,
      session_id TEXT,
      trace_id TEXT,
      details_json TEXT NOT NULL,
      occurred_at REAL NOT NULL,
      recorded_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_relay_audit_when ON data_relay_audit(occurred_at DESC);
    CREATE INDEX IF NOT EXISTS idx_relay_audit_who ON data_relay_audit(who,occurred_at DESC);
    CREATE INDEX IF NOT EXISTS idx_relay_audit_what ON data_relay_audit(what,occurred_at DESC);
    CREATE INDEX IF NOT EXISTS idx_relay_audit_trace ON data_relay_audit(trace_id);
    '''); c.commit(); c.close()
init()

class AuditIn(BaseModel):
    who:str=Field(min_length=1,max_length=200)
    what:str=Field(min_length=1,max_length=300)
    resource:str=''
    result:str=''
    how_method:str=''
    how_channel:str=''
    ip_address:str=''
    user_agent:str=''
    device_id:str=''
    session_id:str=''
    trace_id:str=''
    occurred_at:float=0
    details:Dict[str,Any]=Field(default_factory=dict)

@router.post('/events')
def write_audit(p:AuditIn,x_access_code:str=Header(default='')):
    require_permission(x_access_code,'shipments:write')
    t=time.time(); occurred=p.occurred_at or t; aid='AUD-'+uuid.uuid4().hex[:16].upper()
    c=conn(); c.execute('INSERT INTO data_relay_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
        aid,p.who,p.what,p.resource,p.result,p.how_method,p.how_channel,p.ip_address,
        p.user_agent,p.device_id,p.session_id,p.trace_id,json.dumps(p.details,separators=(',',':'),ensure_ascii=False),occurred,t
    )); c.commit(); c.close()
    return {'recorded':True,'audit_id':aid,'who':p.who,'what':p.what,'when':occurred,'how':{'method':p.how_method,'channel':p.how_channel,'ip_address':p.ip_address,'user_agent':p.user_agent,'device_id':p.device_id,'session_id':p.session_id},'trace_id':p.trace_id}

@router.get('/events')
def read_audit(who:str='',what:str='',trace_id:str='',since:float=0,limit:int=Query(default=100,ge=1,le=1000),x_access_code:str=Header(default='')):
    require_permission(x_access_code,'shipments:read')
    clauses=[]; args=[]
    for col,val in (('who',who),('what',what),('trace_id',trace_id)):
        if val: clauses.append(f'{col}=?'); args.append(val)
    if since: clauses.append('occurred_at>=?'); args.append(since)
    q='SELECT * FROM data_relay_audit'+((' WHERE '+' AND '.join(clauses)) if clauses else '')+' ORDER BY occurred_at DESC LIMIT ?'; args.append(limit)
    c=conn(); rows=[]
    for r in c.execute(q,args):
        d=dict(r); d['details']=json.loads(d.pop('details_json') or '{}'); d['when']=d['occurred_at']; d['how']={'method':d['how_method'],'channel':d['how_channel'],'ip_address':d['ip_address'],'user_agent':d['user_agent'],'device_id':d['device_id'],'session_id':d['session_id']}; rows.append(d)
    c.close(); return {'results':rows}

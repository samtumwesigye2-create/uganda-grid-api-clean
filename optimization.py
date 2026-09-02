import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from auth import require_permission

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'data_hub.db')
router=APIRouter(prefix='/optimization',tags=['optimization'])

class OptimizeRequest(BaseModel):
    target:str='network'
    strategy:str='balanced'
    max_tasks:int=Field(default=100,ge=1,le=1000)


def conn():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def init_db():
    c=conn(); c.execute('''CREATE TABLE IF NOT EXISTS optimization_runs(id TEXT PRIMARY KEY,target TEXT,strategy TEXT,input_count INTEGER,score REAL,recommendations TEXT,created_at REAL)'''); c.commit(); c.close()
init_db()

def access(code,perm='shipments:read'): require_permission(code,perm)

def table_exists(c,name): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def count(c,table,where='1=1'):
    if not table_exists(c,table): return 0
    try:return c.execute(f'SELECT COUNT(*) n FROM {table} WHERE {where}').fetchone()['n']
    except Exception:return 0

def snapshot(c):
    return {
      'orders_active':count(c,'orders',"status NOT IN ('delivered','cancelled','returned')"),
      'orders_picking':count(c,'orders',"status IN ('allocated','picking','packed','ready_to_ship')"),
      'shipments_active':count(c,'shipments',"status NOT IN ('delivered','cancelled')"),
      'yard_units':count(c,'yard_units',"status NOT IN ('departed','cancelled')"),
      'yard_waiting':count(c,'yard_units',"status IN ('expected','checked_in','staged')"),
      'products':count(c,'products'),
      'warehouses':count(c,'warehouses',"is_active=1")
    }

def recommendations(s):
    r=[]
    if s['orders_picking']>10:r.append({'area':'warehouse','priority':'high','action':'Split picking workload into parallel waves','estimated_gain_pct':min(25,5+s['orders_picking']//5)})
    if s['yard_waiting']>5:r.append({'area':'yard','priority':'high','action':'Prioritize checked-in/staged units and free occupied dock capacity','estimated_gain_pct':min(20,5+s['yard_waiting'])})
    if s['shipments_active']>20:r.append({'area':'transport','priority':'medium','action':'Batch active shipments by destination/ZIPPER and dispatch window','estimated_gain_pct':12})
    if s['orders_active']>20:r.append({'area':'orders','priority':'medium','action':'Sequence orders by readiness, warehouse and shipment handoff','estimated_gain_pct':10})
    if not r:r.append({'area':'network','priority':'normal','action':'Maintain balanced workload; no major bottleneck detected','estimated_gain_pct':3})
    return r

@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
    access(x_access_code); c=conn(); s=snapshot(c); rec=recommendations(s); c.close()
    return {'snapshot':s,'recommendations':rec,'optimization_score':max(0,100-s['yard_waiting']*2-s['orders_picking']), 'generated_at':time.time()}

@router.post('/run')
def run(payload:OptimizeRequest,x_access_code:str=Header(default='')):
    access(x_access_code,'shipments:write'); c=conn(); s=snapshot(c); rec=recommendations(s)
    input_count=sum(s.values()); penalty=s['yard_waiting']*2+s['orders_picking']+max(0,s['orders_active']-25)*.5; score=round(max(0,100-penalty),1)
    rid='OPT-'+uuid.uuid4().hex[:10].upper(); import json
    c.execute('INSERT INTO optimization_runs VALUES (?,?,?,?,?,?,?)',(rid,payload.target,payload.strategy,input_count,score,json.dumps(rec),time.time())); c.commit(); c.close()
    return {'run_id':rid,'target':payload.target,'strategy':payload.strategy,'score':score,'input_count':input_count,'snapshot':s,'recommendations':rec}

@router.get('/runs')
def runs(x_access_code:str=Header(default='')):
    access(x_access_code); c=conn(); rows=c.execute('SELECT * FROM optimization_runs ORDER BY created_at DESC LIMIT 50').fetchall(); c.close()
    import json
    out=[]
    for r in rows:
        d=dict(r)
        try:d['recommendations']=json.loads(d['recommendations'])
        except Exception:pass
        out.append(d)
    return {'count':len(out),'results':out}

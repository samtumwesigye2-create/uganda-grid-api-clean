import os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException,Query
from pydantic import BaseModel
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');router=APIRouter(prefix='/yard',tags=['yard'])
UNIT_STATUSES={'expected','checked_in','staged','at_dock','loading','unloading','released','departed','cancelled'};BAY_STATUSES={'available','reserved','occupied','blocked','maintenance'};GATE_STATUSES={'open','closed','restricted'}
class YardUnitCreate(BaseModel):unit_number:str;unit_type:str='trailer';carrier:str='';plate_number:str='';shipment_number:str='';order_number:str='';appointment_time:float|None=None;notes:str=''
class YardUnitUpdate(BaseModel):status:str|None=None;bay_id:str|None=None;gate_id:str|None=None;notes:str|None=None
class ResourceCreate(BaseModel):resource_id:str;name:str
class ResourceStatus(BaseModel):status:str
class TransportRelease(BaseModel):driver_id:str='';vehicle_id:str;location_text:str='';latitude:float|None=None;longitude:float|None=None;scheduled_at:float|None=None;notes:str=''
def conn():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def init_db():
 c=conn();c.execute('CREATE TABLE IF NOT EXISTS yard_units (id TEXT PRIMARY KEY,unit_number TEXT UNIQUE NOT NULL,unit_type TEXT NOT NULL,carrier TEXT,plate_number TEXT,shipment_number TEXT,order_number TEXT,appointment_time REAL,status TEXT NOT NULL,bay_id TEXT,gate_id TEXT,checked_in_at REAL,departed_at REAL,notes TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS yard_bays (id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS yard_gates (id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS yard_history (id TEXT PRIMARY KEY,unit_id TEXT,event TEXT NOT NULL,detail TEXT,created_at REAL NOT NULL)');c.commit();c.close()
init_db()
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def log(c,uid,event,detail=''):c.execute('INSERT INTO yard_history VALUES (?,?,?,?,?)',(str(uuid.uuid4()),uid,event,detail[:1000],time.time()))
def get(c,key):return c.execute('SELECT * FROM yard_units WHERE id=? OR unit_number=?',(key,key.upper())).fetchone()
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();total=c.execute("SELECT COUNT(*) n FROM yard_units WHERE status NOT IN ('departed','cancelled')").fetchone()['n'];arr=c.execute("SELECT COUNT(*) n FROM yard_units WHERE status IN ('expected','checked_in')").fetchone()['n'];b=c.execute('SELECT status,COUNT(*) n FROM yard_bays GROUP BY status').fetchall();g=c.execute('SELECT status,COUNT(*) n FROM yard_gates GROUP BY status').fetchall();c.close();return {'active_units':total,'arrivals':arr,'bays':{r['status']:r['n'] for r in b},'gates':{r['status']:r['n'] for r in g}}
@router.post('/units')
def create(payload:YardUnitCreate,x_access_code:str=Header(default='')):
 write(x_access_code);n=payload.unit_number.strip().upper();c=conn()
 if not n:c.close();raise HTTPException(400,'Unit number is required')
 if c.execute('SELECT 1 FROM yard_units WHERE unit_number=?',(n,)).fetchone():c.close();raise HTTPException(409,'Yard unit already exists')
 uid=str(uuid.uuid4());now=time.time();c.execute('INSERT INTO yard_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,n,payload.unit_type.strip().lower() or 'trailer',payload.carrier.strip(),payload.plate_number.strip().upper(),payload.shipment_number.strip().upper(),payload.order_number.strip().upper(),payload.appointment_time,'expected','','',None,None,payload.notes.strip()[:2000],now,now));log(c,uid,'expected','Yard unit created');c.commit();d=dict(get(c,uid));c.close();return d
@router.get('/units')
def units(status:str=Query(default=''),q:str=Query(default=''),limit:int=Query(default=200,ge=1,le=500),x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();w=[];a=[]
 if status:
  if status not in UNIT_STATUSES:c.close();raise HTTPException(400,'Invalid status')
  w.append('status=?');a.append(status)
 if q.strip():t='%'+q.strip()+'%';w.append('(unit_number LIKE ? OR carrier LIKE ? OR plate_number LIKE ? OR shipment_number LIKE ? OR order_number LIKE ?)');a += [t,t,t,t,t]
 a.append(limit);rows=c.execute('SELECT * FROM yard_units'+(' WHERE '+' AND '.join(w) if w else '')+' ORDER BY created_at DESC LIMIT ?',a).fetchall();c.close();return {'count':len(rows),'results':[dict(r) for r in rows]}
@router.get('/units/{unit_id}')
def detail(unit_id:str,x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();r=get(c,unit_id)
 if not r:c.close();raise HTTPException(404,'Yard unit not found')
 d=dict(r);d['history']=[dict(x) for x in c.execute('SELECT event,detail,created_at FROM yard_history WHERE unit_id=? ORDER BY created_at',(r['id'],)).fetchall()];c.close();return d
@router.put('/units/{unit_id}')
def update(unit_id:str,payload:YardUnitUpdate,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();r=get(c,unit_id)
 if not r:c.close();raise HTTPException(404,'Yard unit not found')
 d=dict(r);now=time.time()
 if payload.status is not None:
  s=payload.status.strip().lower()
  if s not in UNIT_STATUSES:c.close();raise HTTPException(400,'Invalid status')
  d['status']=s
  if s=='checked_in' and not d.get('checked_in_at'):d['checked_in_at']=now
  if s=='departed':d['departed_at']=now
 if payload.bay_id is not None:
  bid=payload.bay_id.strip().upper()
  if bid and not c.execute('SELECT 1 FROM yard_bays WHERE id=?',(bid,)).fetchone():c.close();raise HTTPException(404,'Bay not found')
  d['bay_id']=bid
 if payload.gate_id is not None:
  gid=payload.gate_id.strip().upper()
  if gid and not c.execute('SELECT 1 FROM yard_gates WHERE id=?',(gid,)).fetchone():c.close();raise HTTPException(404,'Gate not found')
  d['gate_id']=gid
 if payload.notes is not None:d['notes']=payload.notes.strip()[:2000]
 c.execute('UPDATE yard_units SET status=?,bay_id=?,gate_id=?,checked_in_at=?,departed_at=?,notes=?,updated_at=? WHERE id=?',(d['status'],d['bay_id'],d['gate_id'],d['checked_in_at'],d['departed_at'],d['notes'],now,r['id']));log(c,r['id'],d['status'],f"bay={d['bay_id']} gate={d['gate_id']}");c.commit();z=dict(get(c,r['id']));c.close();return z
@router.post('/units/{unit_id}/transport-release')
def transport_release(unit_id:str,payload:TransportRelease,x_access_code:str=Header(default=''),x_admin_passcode:str=Header(default='')):
 write(x_access_code);c=conn();r=get(c,unit_id)
 if not r:c.close();raise HTTPException(404,'Yard unit not found')
 if r['status'] not in {'staged','at_dock','loading','released'}:c.close();raise HTTPException(409,'Yard unit must be staged, at_dock, loading, or released before transport dispatch')
 v=c.execute('SELECT * FROM vehicles WHERE id=?',(payload.vehicle_id,)).fetchone()
 if not v:c.close();raise HTTPException(404,'Vehicle not found')
 if v['status']=='maintenance':c.close();raise HTTPException(409,'Vehicle is in maintenance')
 driver=None
 if payload.driver_id:
  driver=c.execute('SELECT * FROM drivers WHERE id=? AND is_active=1',(payload.driver_id,)).fetchone()
  if not driver:c.close();raise HTTPException(404,'Active driver not found')
 task_id=str(uuid.uuid4());counter=c.execute('SELECT next_number FROM dispatch_task_counter WHERE id=1').fetchone();n=counter['next_number'] if counter else 1
 if counter:c.execute('UPDATE dispatch_task_counter SET next_number=? WHERE id=1',(n+1,))
 else:c.execute('INSERT INTO dispatch_task_counter (id,next_number) VALUES (1,2)')
 task_number=f'UG-TASK-{n:06d}';location=(payload.location_text.strip() or r['unit_number']);ship=r['shipment_number'] or ''
 c.execute('INSERT INTO dispatch_tasks (id,task_number,shipment_number,task_type,location_text,latitude,longitude,driver_id,vehicle_id,status,notes,scheduled_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(task_id,task_number,ship or None,'dropoff_customer',location,payload.latitude,payload.longitude,payload.driver_id or None,payload.vehicle_id,'assigned',(payload.notes or f"Yard release {r['unit_number']} / order {r['order_number']}")[:2000],payload.scheduled_at,time.time()));c.execute('INSERT INTO dispatch_task_history (id,task_id,status,note,photo_url,created_at) VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),task_id,'assigned',f"Created from yard unit {r['unit_number']}",None,time.time()));c.execute("UPDATE vehicles SET status='in_use' WHERE id=?",(payload.vehicle_id,));c.execute("UPDATE yard_units SET status='departed',departed_at=?,updated_at=? WHERE id=?",(time.time(),time.time(),r['id']));log(c,r['id'],'departed',f'Transport {task_number}; vehicle={payload.vehicle_id}; driver={payload.driver_id or "unassigned"}')
 if r['order_number']:c.execute("UPDATE orders SET status='shipped',updated_at=? WHERE order_number=?",(time.time(),r['order_number']));c.execute('INSERT INTO order_history VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),c.execute('SELECT id FROM orders WHERE order_number=?',(r['order_number'],)).fetchone()['id'],'transport_dispatched',task_number,'yard-management',time.time())) if c.execute('SELECT id FROM orders WHERE order_number=?',(r['order_number'],)).fetchone() else None
 c.commit();c.close();return {'yard_unit':r['unit_number'],'order_number':r['order_number'],'task_id':task_id,'task_number':task_number,'vehicle_id':payload.vehicle_id,'driver_id':payload.driver_id or None,'status':'assigned'}
@router.post('/bays')
def create_bay(payload:ResourceCreate,x_access_code:str=Header(default='')):
 write(x_access_code);rid=payload.resource_id.strip().upper();name=payload.name.strip()
 if not rid or not name:raise HTTPException(400,'Bay id and name are required')
 c=conn();now=time.time()
 try:c.execute('INSERT INTO yard_bays VALUES (?,?,?,?,?)',(rid,name,'available',now,now));c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Bay already exists')
 c.close();return {'id':rid,'name':name,'status':'available'}
@router.get('/bays')
def bays(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=c.execute('SELECT * FROM yard_bays ORDER BY id').fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.put('/bays/{bay_id}/status')
def bay_status(bay_id:str,payload:ResourceStatus,x_access_code:str=Header(default='')):
 write(x_access_code);s=payload.status.strip().lower()
 if s not in BAY_STATUSES:raise HTTPException(400,'Invalid bay status')
 c=conn();r=c.execute('UPDATE yard_bays SET status=?,updated_at=? WHERE id=?',(s,time.time(),bay_id.upper()));c.commit();c.close()
 if not r.rowcount:raise HTTPException(404,'Bay not found')
 return {'id':bay_id.upper(),'status':s}
@router.post('/gates')
def create_gate(payload:ResourceCreate,x_access_code:str=Header(default='')):
 write(x_access_code);rid=payload.resource_id.strip().upper();name=payload.name.strip();c=conn();now=time.time()
 if not rid or not name:c.close();raise HTTPException(400,'Gate id and name are required')
 try:c.execute('INSERT INTO yard_gates VALUES (?,?,?,?,?)',(rid,name,'open',now,now));c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Gate already exists')
 c.close();return {'id':rid,'name':name,'status':'open'}
@router.get('/gates')
def gates(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=c.execute('SELECT * FROM yard_gates ORDER BY id').fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.put('/gates/{gate_id}/status')
def gate_status(gate_id:str,payload:ResourceStatus,x_access_code:str=Header(default='')):
 write(x_access_code);s=payload.status.strip().lower()
 if s not in GATE_STATUSES:raise HTTPException(400,'Invalid gate status')
 c=conn();r=c.execute('UPDATE yard_gates SET status=?,updated_at=? WHERE id=?',(s,time.time(),gate_id.upper()));c.commit();c.close()
 if not r.rowcount:raise HTTPException(404,'Gate not found')
 return {'id':gate_id.upper(),'status':s}
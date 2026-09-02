import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/robotics',tags=['robotics'])
def c():x=sqlite3.connect(DB);x.row_factory=sqlite3.Row;return x
def exists(x,t):return x.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None
def init():
 x=c();x.executescript('''
 CREATE TABLE IF NOT EXISTS robots(id TEXT PRIMARY KEY,name TEXT NOT NULL,robot_type TEXT NOT NULL,warehouse_id TEXT,status TEXT NOT NULL DEFAULT 'idle',battery REAL DEFAULT 100,last_seen REAL,created_at REAL);
 CREATE TABLE IF NOT EXISTS robot_missions(id TEXT PRIMARY KEY,robot_id TEXT,mission_type TEXT,reference TEXT,source_location TEXT,destination_location TEXT,priority TEXT,status TEXT,created_at REAL,updated_at REAL);
 CREATE TABLE IF NOT EXISTS robot_fleet_managers(id TEXT PRIMARY KEY,name TEXT NOT NULL,vendor TEXT NOT NULL,protocol TEXT NOT NULL,endpoint TEXT,warehouse_id TEXT,status TEXT NOT NULL DEFAULT 'online',last_seen REAL,created_at REAL);
 CREATE TABLE IF NOT EXISTS robot_adapters(id TEXT PRIMARY KEY,fleet_manager_id TEXT,vendor TEXT NOT NULL,adapter_type TEXT NOT NULL,capabilities TEXT,status TEXT NOT NULL DEFAULT 'ready',created_at REAL);
 CREATE TABLE IF NOT EXISTS robot_workspace_reservations(id TEXT PRIMARY KEY,robot_id TEXT,zone TEXT,start_at REAL,end_at REAL,status TEXT NOT NULL,created_at REAL);
 CREATE TABLE IF NOT EXISTS robot_exceptions(id TEXT PRIMARY KEY,mission_id TEXT,robot_id TEXT,exception_type TEXT,detail TEXT,resolution TEXT,status TEXT,created_at REAL,resolved_at REAL);
 CREATE TABLE IF NOT EXISTS robot_decisions(id TEXT PRIMARY KEY,decision_type TEXT,input_json TEXT,decision_json TEXT,created_at REAL);
 ''');x.commit();x.close()
init()
class RobotIn(BaseModel):name:str;robot_type:str='mobile';warehouse_id:str='main'
class MissionIn(BaseModel):robot_id:str='';mission_type:str='move';reference:str='';source_location:str='';destination_location:str='';priority:str='normal'
class StatusIn(BaseModel):status:str
class FleetManagerIn(BaseModel):name:str;vendor:str;protocol:str='REST';endpoint:str='';warehouse_id:str='main'
class AdapterIn(BaseModel):fleet_manager_id:str;vendor:str;adapter_type:str='REST';capabilities:list[str]=[]
class DecisionIn(BaseModel):mission_type:str='move';warehouse_id:str='main';reference:str='';source_location:str='';destination_location:str='';priority:str='normal';worker_available:int=0;traffic_level:str='normal';inventory_demand:float=0;blocked_zones:list[str]=[]
class ExceptionIn(BaseModel):mission_id:str='';robot_id:str='';exception_type:str;detail:str='';blocked_zone:str='';traffic_level:str='normal'
class ReservationIn(BaseModel):robot_id:str;zone:str;duration_seconds:int=Field(default=60,ge=5,le=3600)
def auth(code,p='inventory:read'):require_permission(code,p)
def qcount(x,sql):
 try:return x.execute(sql).fetchone()['n']
 except Exception:return 0
def available_robots(x,warehouse_id='main'):
 rows=x.execute("SELECT * FROM robots WHERE warehouse_id=? AND status='idle' AND battery>=20 ORDER BY battery DESC,last_seen DESC",(warehouse_id,)).fetchall()
 return [dict(r) for r in rows]
def active_reservations(x):return [dict(r) for r in x.execute("SELECT * FROM robot_workspace_reservations WHERE status='active' AND end_at>? ORDER BY start_at",(time.time(),)).fetchall()]
def zone_conflict(x,zone,start,end,exclude_robot=''):
 return x.execute("SELECT 1 FROM robot_workspace_reservations WHERE zone=? AND status='active' AND end_at>? AND start_at<? AND robot_id!=? LIMIT 1",(zone,start,end,exclude_robot)).fetchone() is not None
def choose_robot(x,p):
 bots=available_robots(x,p.warehouse_id);blocked=set(z.lower() for z in p.blocked_zones)
 scored=[]
 for b in bots:
  score=float(b.get('battery') or 0)
  if p.priority=='high':score+=15
  if p.traffic_level=='high':score-=8
  if p.inventory_demand>0:score+=min(20,p.inventory_demand/10)
  if p.destination_location.lower() in blocked or p.source_location.lower() in blocked:score-=100
  score-=sum(12 for r in active_reservations(x) if r['robot_id']==b['id'])
  scored.append((score,b))
 scored.sort(key=lambda z:z[0],reverse=True)
 return scored[0] if scored else (None,None)
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 auth(x_access_code);x=c();out={'robots':qcount(x,'SELECT COUNT(*) n FROM robots'),'online':qcount(x,"SELECT COUNT(*) n FROM robots WHERE status!='offline'"),'active_missions':qcount(x,"SELECT COUNT(*) n FROM robot_missions WHERE status IN ('queued','assigned','running')"),'charging':qcount(x,"SELECT COUNT(*) n FROM robots WHERE status='charging'"),'fleet_managers':qcount(x,"SELECT COUNT(*) n FROM robot_fleet_managers WHERE status='online'"),'adapters':qcount(x,"SELECT COUNT(*) n FROM robot_adapters WHERE status='ready'"),'open_exceptions':qcount(x,"SELECT COUNT(*) n FROM robot_exceptions WHERE status='open'"),'workspace_reservations':qcount(x,"SELECT COUNT(*) n FROM robot_workspace_reservations WHERE status='active' AND end_at>strftime('%s','now')")};x.close();return out
@router.get('/orchestration/state')
def orchestration_state(x_access_code:str=Header(default='')):
 auth(x_access_code);x=c();stock_pressure=qcount(x,"SELECT COUNT(*) n FROM products p WHERE COALESCE((SELECT SUM(s.quantity_on_hand) FROM stock s WHERE s.product_sku=p.sku),0)<=p.reorder_point") if exists(x,'products') and exists(x,'stock') else 0;yard_wait=qcount(x,"SELECT COUNT(*) n FROM yard_units WHERE status IN ('expected','checked_in','staged')") if exists(x,'yard_units') else 0;active_orders=qcount(x,"SELECT COUNT(*) n FROM orders WHERE status NOT IN ('delivered','cancelled','returned')") if exists(x,'orders') else 0;out={'central_coordinator':'UGAMAP Robotics Orchestration','decision_engine':'adaptive_rules_v2','ai_model_connected':False,'ai_ready':True,'signals':{'low_stock_skus':stock_pressure,'yard_waiting':yard_wait,'active_orders':active_orders},'fleet_managers':[dict(r) for r in x.execute('SELECT * FROM robot_fleet_managers ORDER BY name').fetchall()],'workspace_reservations':active_reservations(x)};x.close();return out
@router.get('/robots')
def robots(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robots ORDER BY name').fetchall()];x.close();return {'results':r}
@router.post('/robots')
def add_robot(p:RobotIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');rid='BOT-'+uuid.uuid4().hex[:6].upper();now=time.time();x=c();x.execute('INSERT INTO robots VALUES (?,?,?,?,?,?,?,?)',(rid,p.name,p.robot_type,p.warehouse_id,'idle',100,now,now));x.commit();x.close();return {'id':rid,'status':'idle'}
@router.post('/robots/{rid}/status')
def robot_status(rid:str,p:StatusIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');allowed={'idle','busy','charging','maintenance','offline'}
 if p.status not in allowed:raise HTTPException(400,'Invalid robot status')
 x=c();cur=x.execute('UPDATE robots SET status=?,last_seen=? WHERE id=?',(p.status,time.time(),rid));x.commit();x.close()
 if not cur.rowcount:raise HTTPException(404,'Robot not found')
 return {'id':rid,'status':p.status}
@router.get('/fleet-managers')
def fleet_managers(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robot_fleet_managers ORDER BY name').fetchall()];x.close();return {'results':r}
@router.post('/fleet-managers')
def add_fleet_manager(p:FleetManagerIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');fid='FM-'+uuid.uuid4().hex[:8].upper();now=time.time();x=c();x.execute('INSERT INTO robot_fleet_managers VALUES (?,?,?,?,?,?,?,?,?)',(fid,p.name,p.vendor,p.protocol,p.endpoint,p.warehouse_id,'online',now,now));x.commit();x.close();return {'id':fid,'status':'online'}
@router.get('/adapters')
def adapters(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robot_adapters ORDER BY vendor').fetchall()];x.close();return {'results':r}
@router.post('/adapters')
def add_adapter(p:AdapterIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();fm=x.execute('SELECT id FROM robot_fleet_managers WHERE id=?',(p.fleet_manager_id,)).fetchone()
 if not fm:x.close();raise HTTPException(404,'Fleet manager not found')
 aid='ADP-'+uuid.uuid4().hex[:8].upper();x.execute('INSERT INTO robot_adapters VALUES (?,?,?,?,?,?,?)',(aid,p.fleet_manager_id,p.vendor,p.adapter_type,json.dumps(p.capabilities),'ready',time.time()));x.commit();x.close();return {'id':aid,'status':'ready'}
@router.get('/missions')
def missions(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robot_missions ORDER BY created_at DESC LIMIT 200').fetchall()];x.close();return {'results':r}
@router.post('/missions')
def mission(p:MissionIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();rid=p.robot_id
 if not rid:
  _,bot=choose_robot(x,DecisionIn(mission_type=p.mission_type,warehouse_id='main',reference=p.reference,source_location=p.source_location,destination_location=p.destination_location,priority=p.priority))
  if not bot:x.close();raise HTTPException(409,'No available robot')
  rid=bot['id']
 bot=x.execute('SELECT * FROM robots WHERE id=?',(rid,)).fetchone()
 if not bot:x.close();raise HTTPException(404,'Robot not found')
 if bot['status'] in ('offline','maintenance'):x.close();raise HTTPException(409,'Robot unavailable')
 mid='MIS-'+uuid.uuid4().hex[:8].upper();now=time.time();x.execute('INSERT INTO robot_missions VALUES (?,?,?,?,?,?,?,?,?,?)',(mid,rid,p.mission_type,p.reference,p.source_location,p.destination_location,p.priority,'queued',now,now));x.execute("UPDATE robots SET status='busy',last_seen=? WHERE id=?",(now,rid));x.commit();x.close();return {'id':mid,'robot_id':rid,'status':'queued'}
@router.post('/decision')
def decision(p:DecisionIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();score,bot=choose_robot(x,p);signals={'worker_available':p.worker_available,'traffic_level':p.traffic_level,'inventory_demand':p.inventory_demand,'blocked_zones':p.blocked_zones};decision={'action':'assign_robot' if bot else 'hold','robot_id':bot['id'] if bot else None,'score':score,'reason':'best available robot after battery, workload, traffic, demand and blockage scoring' if bot else 'no safe available robot'};did='DEC-'+uuid.uuid4().hex[:8].upper();x.execute('INSERT INTO robot_decisions VALUES (?,?,?,?,?)',(did,'real_time_assignment',json.dumps(signals),json.dumps(decision),time.time()));x.commit();x.close();return {'decision_id':did,'engine':'adaptive_rules_v2','ai_model_connected':False,'signals':signals,'decision':decision}
@router.post('/workspace/reserve')
def reserve(p:ReservationIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();start=time.time();end=start+p.duration_seconds
 if zone_conflict(x,p.zone,start,end,p.robot_id):x.close();raise HTTPException(409,'Workspace zone already reserved by another robot')
 rid='RSV-'+uuid.uuid4().hex[:8].upper();x.execute('INSERT INTO robot_workspace_reservations VALUES (?,?,?,?,?,?,?)',(rid,p.robot_id,p.zone,start,end,'active',start));x.commit();x.close();return {'id':rid,'zone':p.zone,'status':'active','end_at':end}
@router.post('/exceptions')
def exception(p:ExceptionIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();resolution='hold_and_alert';status='open'
 if p.exception_type in ('path_blocked','traffic_blockage'):
  resolution='reroute_around_'+(p.blocked_zone or 'blocked_zone');status='resolved'
 elif p.exception_type in ('robot_fault','battery_low'):
  resolution='reassign_mission_to_available_robot';status='resolved'
 elif p.exception_type in ('workflow_disruption','worker_unavailable'):
  resolution='resequenced_workflow_and_deferred_human_step';status='resolved'
 eid='EXC-'+uuid.uuid4().hex[:8].upper();now=time.time();x.execute('INSERT INTO robot_exceptions VALUES (?,?,?,?,?,?,?,?,?)',(eid,p.mission_id,p.robot_id,p.exception_type,p.detail,resolution,status,now,now if status=='resolved' else None));x.commit();x.close();return {'id':eid,'status':status,'resolution':resolution,'engine':'adaptive_exception_rules_v2','ai_model_connected':False}
@router.get('/exceptions')
def exceptions(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robot_exceptions ORDER BY created_at DESC LIMIT 100').fetchall()];x.close();return {'results':r}
@router.post('/missions/{mid}/status')
def mission_status(mid:str,p:StatusIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');allowed={'queued','assigned','running','completed','failed','cancelled'}
 if p.status not in allowed:raise HTTPException(400,'Invalid mission status')
 x=c();m=x.execute('SELECT robot_id FROM robot_missions WHERE id=?',(mid,)).fetchone()
 if not m:x.close();raise HTTPException(404,'Mission not found')
 x.execute('UPDATE robot_missions SET status=?,updated_at=? WHERE id=?',(p.status,time.time(),mid))
 if p.status in ('completed','failed','cancelled'):x.execute("UPDATE robots SET status='idle',last_seen=? WHERE id=?",(time.time(),m['robot_id']))
 x.commit();x.close();return {'id':mid,'status':p.status}

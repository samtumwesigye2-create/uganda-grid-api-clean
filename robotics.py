import os,sqlite3,time,uuid
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/robotics',tags=['robotics'])
def c():x=sqlite3.connect(DB);x.row_factory=sqlite3.Row;return x
def init():
 x=c();x.executescript('''CREATE TABLE IF NOT EXISTS robots(id TEXT PRIMARY KEY,name TEXT NOT NULL,robot_type TEXT NOT NULL,warehouse_id TEXT,status TEXT NOT NULL DEFAULT 'idle',battery REAL DEFAULT 100,last_seen REAL,created_at REAL);CREATE TABLE IF NOT EXISTS robot_missions(id TEXT PRIMARY KEY,robot_id TEXT,mission_type TEXT,reference TEXT,source_location TEXT,destination_location TEXT,priority TEXT,status TEXT,created_at REAL,updated_at REAL);''');x.commit();x.close()
init()
class RobotIn(BaseModel):name:str;robot_type:str='mobile';warehouse_id:str='main'
class MissionIn(BaseModel):robot_id:str;mission_type:str='move';reference:str='';source_location:str='';destination_location:str='';priority:str='normal'
class StatusIn(BaseModel):status:str
def auth(code,p='inventory:read'):require_permission(code,p)
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 auth(x_access_code);x=c();total=x.execute('SELECT COUNT(*) n FROM robots').fetchone()['n'];online=x.execute("SELECT COUNT(*) n FROM robots WHERE status!='offline'").fetchone()['n'];active=x.execute("SELECT COUNT(*) n FROM robot_missions WHERE status IN ('queued','assigned','running')").fetchone()['n'];charging=x.execute("SELECT COUNT(*) n FROM robots WHERE status='charging'").fetchone()['n'];x.close();return {'robots':total,'online':online,'active_missions':active,'charging':charging}
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
@router.get('/missions')
def missions(x_access_code:str=Header(default='')):auth(x_access_code);x=c();r=[dict(z) for z in x.execute('SELECT * FROM robot_missions ORDER BY created_at DESC LIMIT 200').fetchall()];x.close();return {'results':r}
@router.post('/missions')
def mission(p:MissionIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');x=c();bot=x.execute('SELECT * FROM robots WHERE id=?',(p.robot_id,)).fetchone()
 if not bot: x.close();raise HTTPException(404,'Robot not found')
 if bot['status'] in ('offline','maintenance'):x.close();raise HTTPException(409,'Robot unavailable')
 mid='MIS-'+uuid.uuid4().hex[:8].upper();now=time.time();x.execute('INSERT INTO robot_missions VALUES (?,?,?,?,?,?,?,?,?,?)',(mid,p.robot_id,p.mission_type,p.reference,p.source_location,p.destination_location,p.priority,'queued',now,now));x.execute("UPDATE robots SET status='busy',last_seen=? WHERE id=?",(now,p.robot_id));x.commit();x.close();return {'id':mid,'robot_id':p.robot_id,'status':'queued'}
@router.post('/missions/{mid}/status')
def mission_status(mid:str,p:StatusIn,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');allowed={'queued','assigned','running','completed','failed','cancelled'}
 if p.status not in allowed:raise HTTPException(400,'Invalid mission status')
 x=c();m=x.execute('SELECT robot_id FROM robot_missions WHERE id=?',(mid,)).fetchone()
 if not m:x.close();raise HTTPException(404,'Mission not found')
 x.execute('UPDATE robot_missions SET status=?,updated_at=? WHERE id=?',(p.status,time.time(),mid))
 if p.status in ('completed','failed','cancelled'):x.execute("UPDATE robots SET status='idle',last_seen=? WHERE id=?",(time.time(),m['robot_id']))
 x.commit();x.close();return {'id':mid,'status':p.status}

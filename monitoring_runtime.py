"""UGAMAP Monitoring Service: health probes, performance samples, incidents and alert rules."""
import os,sqlite3,time,uuid,shutil
from fastapi import APIRouter,Header
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/platform/monitoring-runtime',tags=['platform-monitoring'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read(code):require_permission(code,'shipments:read')
def write(code):require_permission(code,'shipments:write')
def now():return time.time()
def init():
 c=conn();c.executescript('''CREATE TABLE IF NOT EXISTS platform_monitor_services(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,target TEXT,status TEXT NOT NULL DEFAULT 'unknown',last_latency_ms REAL,last_error TEXT,last_checked_at REAL,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_monitor_samples(id TEXT PRIMARY KEY,service_id TEXT NOT NULL,status TEXT NOT NULL,latency_ms REAL,metric_name TEXT,metric_value REAL,detail TEXT,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_monitor_alert_rules(id TEXT PRIMARY KEY,name TEXT NOT NULL,metric_name TEXT NOT NULL,operator TEXT NOT NULL,threshold REAL NOT NULL,severity TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS platform_monitor_incidents(id TEXT PRIMARY KEY,service_id TEXT,title TEXT NOT NULL,severity TEXT NOT NULL,status TEXT NOT NULL,detail TEXT,opened_at REAL NOT NULL,resolved_at REAL);''');c.commit();c.close()
init()
class ServiceIn(BaseModel):name:str;kind:str='application';target:str='internal'
class SampleIn(BaseModel):service_id:str;status:str='healthy';latency_ms:float=0;metric_name:str='response_ms';metric_value:float=0;detail:str=''
class RuleIn(BaseModel):name:str;metric_name:str;operator:str='>';threshold:float;severity:str='warning'
class IncidentIn(BaseModel):service_id:str='';title:str;severity:str='warning';detail:str=''
def breached(op,v,t):return {'>':v>t,'>=':v>=t,'<':v<t,'<=':v<=t,'==':v==t}.get(op,False)
@router.post('/services')
def add_service(p:ServiceIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();sid='MON-'+uuid.uuid4().hex[:8].upper();t=now();c.execute('INSERT OR REPLACE INTO platform_monitor_services VALUES (?,?,?,?,?,?,?,?,?)',(sid,p.name,p.kind,p.target,'unknown',None,'',None,t));c.commit();c.close();return {'id':sid,**(p.model_dump() if hasattr(p,'model_dump') else p.dict())}
@router.get('/services')
def services(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_monitor_services ORDER BY name')];c.close();return {'results':r}
@router.post('/samples')
def sample(p:SampleIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();t=now();c.execute('INSERT INTO platform_monitor_samples VALUES (?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),p.service_id,p.status,p.latency_ms,p.metric_name,p.metric_value,p.detail,t));c.execute('UPDATE platform_monitor_services SET status=?,last_latency_ms=?,last_error=?,last_checked_at=? WHERE id=?',(p.status,p.latency_ms,p.detail if p.status not in ('healthy','ok','up') else '',t,p.service_id));alerts=[]
 for r in c.execute('SELECT * FROM platform_monitor_alert_rules WHERE is_active=1 AND metric_name=?',(p.metric_name,)):
  if breached(r['operator'],p.metric_value,r['threshold']):
   iid='INC-'+uuid.uuid4().hex[:8].upper();title=f"{r['name']}: {p.metric_name} {p.metric_value} {r['operator']} {r['threshold']}";c.execute('INSERT INTO platform_monitor_incidents VALUES (?,?,?,?,?,?,?,?)',(iid,p.service_id,title,r['severity'],'open',p.detail,t,None));alerts.append(iid)
 c.commit();c.close();return {'recorded':True,'alerts':alerts}
@router.post('/rules')
def rule(p:RuleIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();rid='ALR-'+uuid.uuid4().hex[:8].upper();c.execute('INSERT INTO platform_monitor_alert_rules VALUES (?,?,?,?,?,?,?,?)',(rid,p.name,p.metric_name,p.operator,p.threshold,p.severity,1,now()));c.commit();c.close();return {'id':rid,**(p.model_dump() if hasattr(p,'model_dump') else p.dict())}
@router.get('/rules')
def rules(x_access_code:str=Header(default='')):read(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM platform_monitor_alert_rules ORDER BY created_at DESC')];c.close();return {'results':r}
@router.post('/incidents')
def incident(p:IncidentIn,x_access_code:str=Header(default='')):
 write(x_access_code);c=conn();iid='INC-'+uuid.uuid4().hex[:8].upper();c.execute('INSERT INTO platform_monitor_incidents VALUES (?,?,?,?,?,?,?,?)',(iid,p.service_id,p.title,p.severity,'open',p.detail,now(),None));c.commit();c.close();return {'id':iid,'status':'open'}
@router.post('/incidents/{incident_id}/resolve')
def resolve(incident_id:str,x_access_code:str=Header(default='')):write(x_access_code);c=conn();n=c.execute("UPDATE platform_monitor_incidents SET status='resolved',resolved_at=? WHERE id=?",(now(),incident_id)).rowcount;c.commit();c.close();return {'resolved':bool(n),'id':incident_id}
@router.get('/incidents')
def incidents(status:str='',x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();q='SELECT * FROM platform_monitor_incidents';a=[]
 if status:q+=' WHERE status=?';a.append(status)
 r=[dict(x) for x in c.execute(q+' ORDER BY opened_at DESC',a)];c.close();return {'results':r}
@router.get('/system')
def system(x_access_code:str=Header(default='')):
 read(x_access_code);t0=time.perf_counter();c=conn();c.execute('SELECT 1').fetchone();db_ms=(time.perf_counter()-t0)*1000;c.close();disk=shutil.disk_usage(BASE);load=os.getloadavg() if hasattr(os,'getloadavg') else None;db_size=os.path.getsize(DB) if os.path.exists(DB) else 0;return {'status':'healthy','database_latency_ms':round(db_ms,3),'database_size_bytes':db_size,'disk_total_bytes':disk.total,'disk_used_bytes':disk.used,'disk_free_bytes':disk.free,'load_average':load,'process_id':os.getpid(),'timestamp':now(),'note':'Host CPU percentage and memory telemetry require host/runtime metrics integration.'}
@router.get('/dashboard')
def dashboard(x_access_code:str=Header(default='')):
 read(x_access_code);c=conn();svc=c.execute('SELECT COUNT(*) n,SUM(CASE WHEN status IN ("healthy","ok","up") THEN 1 ELSE 0 END) healthy FROM platform_monitor_services').fetchone();inc=c.execute("SELECT COUNT(*) n FROM platform_monitor_incidents WHERE status='open'").fetchone()['n'];samples=[dict(x) for x in c.execute('SELECT service_id,status,latency_ms,metric_name,metric_value,detail,created_at FROM platform_monitor_samples ORDER BY created_at DESC LIMIT 100')];c.close();return {'services':dict(svc),'open_incidents':inc,'recent_samples':samples}
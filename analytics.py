import math, os, sqlite3, time, uuid
from collections import defaultdict
from fastapi import APIRouter, Header, Query, HTTPException
from pydantic import BaseModel
from auth import require_permission

BASE_DIR=os.path.dirname(os.path.abspath(__file__)); DB_PATH=os.path.join(BASE_DIR,'data_hub.db')
router=APIRouter(prefix='/analytics',tags=['analytics'])

def conn():
 c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

def table_exists(c,n): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None

def safe_rows(c,q,a=()):
 try:return [dict(x) for x in c.execute(q,a).fetchall()]
 except Exception:return []

def access(code,p='shipments:read'): require_permission(code,p)

def init_db():
 c=conn(); c.executescript('''
 CREATE TABLE IF NOT EXISTS analytics_runs(id TEXT PRIMARY KEY,model TEXT NOT NULL,window_days INTEGER NOT NULL,signals INTEGER NOT NULL,anomalies INTEGER NOT NULL,created_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS vehicle_telematics(id INTEGER PRIMARY KEY AUTOINCREMENT,vehicle_id TEXT,odometer_km REAL,fuel_liters REAL,idle_minutes REAL,engine_temp_c REAL,battery_v REAL,fault_code TEXT,load_kg REAL,driver_score REAL,recorded_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS external_operational_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,signal_type TEXT,area TEXT,severity REAL,value REAL,details TEXT,recorded_at REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS delivery_presence_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,reference TEXT,zipper TEXT,hour_local INTEGER,weekday INTEGER,success INTEGER,recorded_at REAL NOT NULL);
 '''); c.commit(); c.close()
init_db()

class TelemetryIn(BaseModel):
 vehicle_id:str; odometer_km:float=0; fuel_liters:float=0; idle_minutes:float=0; engine_temp_c:float=0; battery_v:float=0; fault_code:str=''; load_kg:float=0; driver_score:float=0
class ExternalSignalIn(BaseModel):
 signal_type:str; area:str='network'; severity:float=0; value:float=0; details:str=''
class PresenceSignalIn(BaseModel):
 reference:str=''; zipper:str=''; hour_local:int; weekday:int; success:bool

def day_key(ts): return time.strftime('%Y-%m-%d',time.localtime(float(ts)))
def order_series(c,window_days):
 now=time.time(); start=now-window_days*86400; counts=defaultdict(float); values=defaultdict(float)
 if table_exists(c,'orders'):
  for r in safe_rows(c,'SELECT created_at,subtotal,status FROM orders WHERE created_at>=?',(start,)):
   if r.get('status')=='cancelled':continue
   k=day_key(r.get('created_at',now)); counts[k]+=1; values[k]+=float(r.get('subtotal') or 0)
 out=[]
 for i in range(window_days):
  k=day_key(start+i*86400); out.append({'date':k,'orders':counts[k],'value':values[k]})
 return out

def forecast_values(series,days):
 ys=[float(x['orders']) for x in series]; n=len(ys)
 if not ys:return [],0.35,0,0
 recent=ys[-min(7,n):]; avg=sum(recent)/len(recent); trend=0
 if n>=2:
  xb=(n-1)/2; yb=sum(ys)/n; den=sum((i-xb)**2 for i in range(n)) or 1; trend=sum((i-xb)*(y-yb) for i,y in enumerate(ys))/den
 result=[{'date':day_key(time.time()+i*86400),'predicted_orders':round(max(0,avg+trend*i),2)} for i in range(1,days+1)]
 mean=sum(ys)/n; var=sum((y-mean)**2 for y in ys)/max(1,n-1); sd=math.sqrt(var); conf=max(.35,min(.95,1-(sd/(mean+1))*.35))
 return result,round(conf,3),round(trend,3),round(avg,3)

def anomalies(c):
 out=[]
 if table_exists(c,'products') and table_exists(c,'stock'):
  for r in safe_rows(c,"SELECT p.sku,p.name,p.reorder_point,COALESCE(SUM(s.quantity_on_hand),0) qty FROM products p LEFT JOIN stock s ON s.product_sku=p.sku GROUP BY p.sku"):
   qty=float(r.get('qty') or 0); rp=float(r.get('reorder_point') or 0)
   if qty<=rp: out.append({'type':'inventory','severity':'high' if qty<=0 else 'medium','entity':r.get('sku'),'message':f"{r.get('name')} stock {qty:g} is at/below reorder point {rp:g}"})
 if table_exists(c,'orders'):
  cutoff=time.time()-48*3600
  for r in safe_rows(c,"SELECT order_number,status,created_at FROM orders WHERE created_at<? AND status NOT IN ('shipped','delivered','cancelled','returned')",(cutoff,)):
   out.append({'type':'order_delay','severity':'medium','entity':r.get('order_number'),'message':f"Order remains {r.get('status')} after 48+ hours"})
 if table_exists(c,'yard_units'):
  cutoff=time.time()-24*3600
  for r in safe_rows(c,"SELECT unit_number,status,checked_in_at,created_at FROM yard_units WHERE status NOT IN ('departed','cancelled')"):
   anchor=r.get('checked_in_at') or r.get('created_at')
   if anchor and anchor<cutoff: out.append({'type':'yard_dwell','severity':'medium','entity':r.get('unit_number'),'message':f"Yard unit remains {r.get('status')} for 24+ hours"})
 return out

def transport_intelligence(c):
 now=time.time(); tele=safe_rows(c,'SELECT * FROM vehicle_telematics WHERE recorded_at>? ORDER BY recorded_at DESC',(now-30*86400,)); ext=safe_rows(c,'SELECT * FROM external_operational_signals WHERE recorded_at>? ORDER BY recorded_at DESC',(now-6*3600,)); presence=safe_rows(c,'SELECT * FROM delivery_presence_signals WHERE recorded_at>?',(now-180*86400,))
 vehicles={}
 for t in tele:
  vehicles.setdefault(t['vehicle_id'],[]).append(t)
 maintenance=[]; fuel=[]
 for vid,rs in vehicles.items():
  latest=rs[0]; risk=0; reasons=[]
  if float(latest.get('engine_temp_c') or 0)>105:risk+=35;reasons.append('high engine temperature')
  if latest.get('fault_code'):risk+=35;reasons.append('active fault code')
  if 0<float(latest.get('battery_v') or 0)<11.8:risk+=20;reasons.append('low battery voltage')
  if len(rs)>=2 and float(latest.get('odometer_km') or 0)-float(rs[-1].get('odometer_km') or 0)>10000:risk+=10;reasons.append('high recent mileage')
  maintenance.append({'vehicle_id':vid,'risk_score':min(100,risk),'reasons':reasons or ['no strong maintenance risk signal']})
  total_fuel=sum(float(x.get('fuel_liters') or 0) for x in rs); idle=sum(float(x.get('idle_minutes') or 0) for x in rs); load=sum(float(x.get('load_kg') or 0) for x in rs)/max(1,len(rs)); fuel.append({'vehicle_id':vid,'fuel_liters':round(total_fuel,2),'idle_minutes':round(idle,1),'avg_load_kg':round(load,1),'efficiency_flag':'review' if idle>180 else 'normal'})
 traffic=max([float(x.get('severity') or 0) for x in ext if x.get('signal_type')=='traffic'] or [0]); weather=max([float(x.get('severity') or 0) for x in ext if x.get('signal_type')=='weather'] or [0])
 success_by_slot=defaultdict(lambda:[0,0])
 for p in presence:
  k=(int(p.get('weekday') or 0),int(p.get('hour_local') or 0)); success_by_slot[k][1]+=1; success_by_slot[k][0]+=int(p.get('success') or 0)
 best_slots=sorted([{'weekday':k[0],'hour':k[1],'success_rate':round(v[0]/v[1],3),'samples':v[1]} for k,v in success_by_slot.items() if v[1]],key=lambda x:(-x['success_rate'],-x['samples']))[:10]
 return {'predictive_maintenance':maintenance,'fuel_modeling':fuel,'traffic_severity':traffic,'weather_severity':weather,'best_delivery_slots':best_slots,'external_signals':ext[:50]}

@router.post('/telematics')
def ingest_telematics(p:TelemetryIn,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write'); c=conn(); c.execute('INSERT INTO vehicle_telematics(vehicle_id,odometer_km,fuel_liters,idle_minutes,engine_temp_c,battery_v,fault_code,load_kg,driver_score,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)',(p.vehicle_id,p.odometer_km,p.fuel_liters,p.idle_minutes,p.engine_temp_c,p.battery_v,p.fault_code,p.load_kg,p.driver_score,time.time())); c.commit(); c.close(); return {'ok':True}
@router.post('/external-signal')
def ingest_external(p:ExternalSignalIn,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write'); c=conn(); c.execute('INSERT INTO external_operational_signals(signal_type,area,severity,value,details,recorded_at) VALUES (?,?,?,?,?,?)',(p.signal_type,p.area,p.severity,p.value,p.details,time.time())); c.commit(); c.close(); return {'ok':True}
@router.post('/delivery-presence')
def ingest_presence(p:PresenceSignalIn,x_access_code:str=Header(default='')):
 access(x_access_code,'shipments:write'); c=conn(); c.execute('INSERT INTO delivery_presence_signals(reference,zipper,hour_local,weekday,success,recorded_at) VALUES (?,?,?,?,?,?)',(p.reference,p.zipper,p.hour_local,p.weekday,1 if p.success else 0,time.time())); c.commit(); c.close(); return {'ok':True}

@router.get('/last-mile')
def last_mile(x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); intel=transport_intelligence(c); tasks=safe_rows(c,"SELECT * FROM dispatch_tasks WHERE status NOT IN ('completed','cancelled','failed') ORDER BY scheduled_at LIMIT 200") if table_exists(c,'dispatch_tasks') else []; loc=safe_rows(c,'SELECT * FROM driver_location_pings ORDER BY rowid DESC LIMIT 300') if table_exists(c,'driver_location_pings') else []; c.close()
 congestion=intel['traffic_severity']; weather=intel['weather_severity']; route_factor=round(1+0.25*congestion+0.15*weather,2)
 eta_window=max(15,int(20*route_factor)); return {'dynamic_route_optimization':{'active_tasks':len(tasks),'driver_location_signals':len(loc),'traffic_severity':congestion,'weather_severity':weather,'route_cost_factor':route_factor,'method':'real-time heuristic using dispatch, GPS, traffic/weather signals'},'eta_prediction':{'recommended_window_minutes':eta_window,'method':'signal-adjusted operational ETA heuristic'},'failed_delivery_reduction':{'best_delivery_slots':intel['best_delivery_slots'],'presence_samples':sum(x['samples'] for x in intel['best_delivery_slots'])},'trained_ml':False}

@router.get('/fleet-efficiency')
def fleet_efficiency(x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); intel=transport_intelligence(c); vehicles=safe_rows(c,'SELECT * FROM vehicles') if table_exists(c,'vehicles') else []; tasks=safe_rows(c,"SELECT * FROM dispatch_tasks WHERE status NOT IN ('completed','cancelled','failed')") if table_exists(c,'dispatch_tasks') else []; c.close()
 available=[x for x in vehicles if str(x.get('status','')).lower() in ('available','active','idle')]; unassigned=[x for x in tasks if not x.get('vehicle_id')]
 matches=[]
 for i,t in enumerate(unassigned):
  if available: matches.append({'task':t.get('task_number') or t.get('id'),'vehicle_id':available[i%len(available)].get('id'),'reason':'available capacity match'})
 return {'predictive_maintenance':intel['predictive_maintenance'],'fuel_consumption_modeling':intel['fuel_modeling'],'capacity_matching':matches,'vehicles':len(vehicles),'active_tasks':len(tasks),'trained_ml':False}

@router.get('/logistics-planning')
def logistics_planning(window_days:int=Query(default=30,ge=7,le=180),x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); series=order_series(c,window_days); fc,conf,trend,avg=forecast_values(series,28); an=anomalies(c); bottlenecks=[]
 if table_exists(c,'yard_units'):
  grouped=defaultdict(int)
  for r in safe_rows(c,"SELECT bay_id,status FROM yard_units WHERE status NOT IN ('departed','cancelled')"):
   grouped[r.get('bay_id') or 'unassigned']+=1
  for k,v in grouped.items():
   if v>=3:bottlenecks.append({'location':k,'type':'yard/cross-dock pressure','active_units':v,'severity':'high' if v>=8 else 'medium'})
 if table_exists(c,'orders'):
  wh=defaultdict(int)
  for r in safe_rows(c,"SELECT warehouse_id,status FROM orders WHERE status NOT IN ('delivered','cancelled','returned')"):
   wh[r.get('warehouse_id') or 'unassigned']+=1
  for k,v in wh.items():
   if v>=10:bottlenecks.append({'location':k,'type':'warehouse order backlog','active_orders':v,'severity':'high' if v>=30 else 'medium'})
 c.close(); return {'predictive_demand_forecasting':{'forecast_days':28,'confidence':conf,'trend_per_day':trend,'daily_average':avg,'forecast':fc},'bottleneck_detection':bottlenecks,'operational_anomalies':an,'trained_ml':False}

@router.get('/summary')
def summary(window_days:int=Query(default=30,ge=7,le=180),x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); series=order_series(c,window_days); fc,conf,trend,avg=forecast_values(series,7); an=anomalies(c); active_orders=0; shipments=0
 if table_exists(c,'orders'): active_orders=c.execute("SELECT COUNT(*) n FROM orders WHERE status NOT IN ('delivered','cancelled','returned')").fetchone()['n']
 if table_exists(c,'shipments'): shipments=c.execute('SELECT COUNT(*) n FROM shipments').fetchone()['n']
 low=sum(1 for x in an if x['type']=='inventory'); c.close(); return {'window_days':window_days,'active_orders':active_orders,'shipments':shipments,'signals':len(series)+shipments+active_orders,'anomalies':len(an),'low_stock':low,'forecast_confidence':conf,'daily_order_average':avg,'trend_per_day':trend,'forecast_next_7_days':fc}
@router.get('/forecast')
def forecast(days:int=Query(default=7,ge=1,le=30),window_days:int=Query(default=30,ge=7,le=180),x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); series=order_series(c,window_days); c.close(); fc,conf,trend,avg=forecast_values(series,days); return {'model':'moving-average-plus-linear-trend','trained_ml':False,'window_days':window_days,'forecast_days':days,'confidence':conf,'trend_per_day':trend,'daily_order_average':avg,'history':series,'forecast':fc}
@router.get('/anomalies')
def anomaly_list(x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); r=anomalies(c); c.close(); return {'count':len(r),'results':r}
@router.post('/run')
def run_analysis(window_days:int=Query(default=30,ge=7,le=180),x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); series=order_series(c,window_days); fc,conf,trend,avg=forecast_values(series,7); an=anomalies(c); rid='ANL-'+uuid.uuid4().hex[:10].upper(); signals=len(series); c.execute('INSERT INTO analytics_runs(id,model,window_days,signals,anomalies,created_at) VALUES (?,?,?,?,?,?)',(rid,'moving-average-plus-linear-trend',window_days,signals,len(an),time.time())); c.commit(); c.close(); return {'run_id':rid,'model':'moving-average-plus-linear-trend','trained_ml':False,'signals':signals,'anomalies':len(an),'confidence':conf,'trend_per_day':trend,'daily_order_average':avg,'forecast':fc,'results':an}
@router.get('/runs')
def list_runs(limit:int=Query(default=50,ge=1,le=200),x_access_code:str=Header(default='')):
 access(x_access_code); c=conn(); r=c.execute('SELECT * FROM analytics_runs ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall(); c.close(); return {'count':len(r),'results':[dict(x) for x in r]}

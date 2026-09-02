import os,sqlite3,time,uuid,json,statistics
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/visibility',tags=['supply-chain-visibility'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def read_auth(code):require_permission(code,'shipments:read')
def write_auth(code):require_permission(code,'shipments:write')
def exists(c,t):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None
def rows(c,q,a=()):
 try:return [dict(x) for x in c.execute(q,a).fetchall()]
 except Exception:return []
def init():
 c=conn();c.executescript('''
 CREATE TABLE IF NOT EXISTS supply_suppliers(id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT,cost_score REAL DEFAULT 50,quality_score REAL DEFAULT 50,on_time_score REAL DEFAULT 50,risk_score REAL DEFAULT 50,status TEXT DEFAULT 'active',notes TEXT,created_at REAL,updated_at REAL);
 CREATE TABLE IF NOT EXISTS supply_plans(id TEXT PRIMARY KEY,plan_type TEXT NOT NULL,name TEXT NOT NULL,horizon_days INTEGER DEFAULT 30,capacity REAL DEFAULT 0,target_service_level REAL DEFAULT 95,constraints TEXT,status TEXT DEFAULT 'draft',result TEXT,created_at REAL,updated_at REAL);
 CREATE TABLE IF NOT EXISTS supply_network_nodes(id TEXT PRIMARY KEY,name TEXT NOT NULL,node_type TEXT NOT NULL,location TEXT,capacity REAL DEFAULT 0,status TEXT DEFAULT 'active',created_at REAL,updated_at REAL);
 CREATE TABLE IF NOT EXISTS supply_customer_metrics(id TEXT PRIMARY KEY,segment TEXT NOT NULL,availability_pct REAL DEFAULT 100,promise_days REAL DEFAULT 0,cost_to_serve REAL DEFAULT 0,service_quality REAL DEFAULT 100,updated_at REAL);
 ''');c.commit();c.close()
init()
class SupplierIn(BaseModel):name:str;category:str='general';cost_score:float=Field(default=50,ge=0,le=100);quality_score:float=Field(default=50,ge=0,le=100);on_time_score:float=Field(default=50,ge=0,le=100);risk_score:float=Field(default=50,ge=0,le=100);notes:str=''
class PlanIn(BaseModel):plan_type:str;name:str;horizon_days:int=Field(default=30,ge=1,le=365);capacity:float=0;target_service_level:float=Field(default=95,ge=0,le=100);constraints:str=''
class NodeIn(BaseModel):name:str;node_type:str;location:str='';capacity:float=0
class CustomerMetricIn(BaseModel):segment:str;availability_pct:float=100;promise_days:float=0;cost_to_serve:float=0;service_quality:float=100

def live_metrics(c):
 shipments=rows(c,'SELECT shipment_number,status,delivery_status FROM shipments ORDER BY rowid DESC LIMIT 1000') if exists(c,'shipments') else []
 orders=rows(c,'SELECT order_number,status,subtotal,warehouse_id,updated_at FROM orders ORDER BY updated_at DESC LIMIT 1000') if exists(c,'orders') else []
 stock=rows(c,'SELECT product_sku,warehouse_id,quantity_on_hand FROM stock') if exists(c,'stock') else []
 products=rows(c,'SELECT sku,reorder_point FROM products') if exists(c,'products') else []
 yard=rows(c,'SELECT id,status,shipment_number,updated_at FROM yard_units ORDER BY updated_at DESC LIMIT 1000') if exists(c,'yard_units') else []
 warehouses=rows(c,'SELECT id,name,is_active FROM warehouses') if exists(c,'warehouses') else []
 delivered=sum(1 for x in shipments if str(x.get('status','')).lower()=='delivered' or str(x.get('delivery_status','')).lower()=='delivered')
 at_risk=sum(1 for x in shipments if str(x.get('status','')).lower() in ('delayed','exception','failed','held') or str(x.get('delivery_status','')).lower() in ('delayed','exception','failed','held'))
 active_orders=[x for x in orders if x.get('status') not in ('delivered','cancelled','returned')]
 reorder={str(x.get('sku')):float(x.get('reorder_point') or 0) for x in products}
 totals={}
 for x in stock:totals[x.get('product_sku')]=totals.get(x.get('product_sku'),0)+float(x.get('quantity_on_hand') or 0)
 low_stock=[{'sku':sku,'on_hand':qty,'reorder_point':reorder.get(sku,0)} for sku,qty in totals.items() if qty<=reorder.get(sku,0)]
 return {'shipments':shipments,'orders':orders,'active_orders':active_orders,'stock':stock,'low_stock':low_stock,'yard':yard,'warehouses':warehouses,'tracked_shipments':len(shipments),'delivered':delivered,'at_risk':at_risk,'yard_units':sum(1 for x in yard if x.get('status') not in ('departed','cancelled'))}

def demand_forecast(m,horizon=30):
 active=len(m['active_orders']);delivered=m['delivered'];base=max(1,active+max(1,delivered//30));trend=max(-0.25,min(0.5,(active-delivered/max(1,len(m['shipments'])))*0.1));daily=[]
 for d in range(1,min(horizon,90)+1):daily.append({'day':d,'forecast_units':round(base*(1+trend*d/7),1)})
 confidence=max(40,min(95,55+min(30,len(m['orders'])/10)))
 return {'method':'live moving baseline + trend heuristic','horizon_days':horizon,'confidence_pct':round(confidence,1),'daily':daily,'signals':{'active_orders':active,'delivered_shipments':delivered,'at_risk_shipments':m['at_risk'],'low_stock_skus':len(m['low_stock'])}}

def supply_plan(m):
 demand=max(1,len(m['active_orders']));stock_units=sum(float(x.get('quantity_on_hand') or 0) for x in m['stock']);capacity=max(1,len([w for w in m['warehouses'] if w.get('is_active',1)]))*100
 gap=max(0,demand-stock_units);service=max(0,min(100,100-(len(m['low_stock'])*3+m['at_risk']*2)))
 return {'demand_units':demand,'available_stock_units':round(stock_units,1),'capacity_index':capacity,'supply_gap_units':round(gap,1),'service_level_estimate_pct':round(service,1),'constraints':{'low_stock_skus':len(m['low_stock']),'at_risk_shipments':m['at_risk'],'yard_units':m['yard_units']}}

@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();m=live_metrics(c);suppliers=c.execute('SELECT COUNT(*) n FROM supply_suppliers WHERE status="active"').fetchone()['n'];plans=c.execute('SELECT COUNT(*) n FROM supply_plans').fetchone()['n'];nodes=c.execute('SELECT COUNT(*) n FROM supply_network_nodes WHERE status="active"').fetchone()['n'];c.close();return {'tracked_shipments':m['tracked_shipments'],'delivered':m['delivered'],'at_risk':m['at_risk'],'active_orders':len(m['active_orders']),'yard_units':m['yard_units'],'low_stock_skus':len(m['low_stock']),'suppliers':suppliers,'plans':plans,'network_nodes':nodes,'generated_at':time.time()}
@router.get('/network')
def network(q:str='',x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();ship=rows(c,'SELECT shipment_number,status,delivery_status FROM shipments ORDER BY rowid DESC LIMIT 300') if exists(c,'shipments') else [];orders=rows(c,'SELECT order_number,status,shipment_number,delivery_grid_id,warehouse_id,updated_at FROM orders ORDER BY updated_at DESC LIMIT 300') if exists(c,'orders') else [];yard=rows(c,'SELECT * FROM yard_units ORDER BY updated_at DESC LIMIT 300') if exists(c,'yard_units') else [];c.close();needle=q.lower().strip()
 def keep(x):return not needle or needle in ' '.join(str(v) for v in x.values()).lower()
 return {'shipments':[x for x in ship if keep(x)],'orders':[x for x in orders if keep(x)],'yard':[x for x in yard if keep(x)],'generated_at':time.time()}
@router.get('/trace/{reference}')
def trace(reference:str,x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();r='%'+reference+'%';ship=rows(c,'SELECT * FROM shipments WHERE shipment_number LIKE ? LIMIT 20',(r,)) if exists(c,'shipments') else [];orders=rows(c,'SELECT * FROM orders WHERE order_number LIKE ? OR shipment_number LIKE ? OR delivery_grid_id LIKE ? LIMIT 20',(r,r,r)) if exists(c,'orders') else [];yard=rows(c,'SELECT * FROM yard_units WHERE shipment_number LIKE ? OR order_number LIKE ? LIMIT 20',(r,r)) if exists(c,'yard_units') else [];c.close();return {'reference':reference,'shipments':ship,'orders':orders,'yard':yard,'generated_at':time.time()}
@router.get('/demand-planning')
def demand_planning(horizon_days:int=30,x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();m=live_metrics(c);c.close();return demand_forecast(m,horizon_days)
@router.get('/supply-planning')
def supply_planning(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();m=live_metrics(c);c.close();return supply_plan(m)
@router.post('/suppliers')
def add_supplier(p:SupplierIn,x_access_code:str=Header(default='')):
 write_auth(x_access_code);sid='SUP-'+uuid.uuid4().hex[:8].upper();now=time.time();c=conn();c.execute('INSERT INTO supply_suppliers VALUES (?,?,?,?,?,?,?,?,?,?,?)',(sid,p.name,p.category,p.cost_score,p.quality_score,p.on_time_score,p.risk_score,'active',p.notes,now,now));c.commit();c.close();return {'id':sid,'status':'active'}
@router.get('/suppliers')
def suppliers(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM supply_suppliers ORDER BY name').fetchall()];c.close();
 for x in r:x['performance_score']=round((x['cost_score']+x['quality_score']+x['on_time_score']+(100-x['risk_score']))/4,1)
 return {'results':r}
@router.get('/strategic-sourcing')
def strategic_sourcing(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();r=[dict(x) for x in c.execute("SELECT * FROM supply_suppliers WHERE status='active'").fetchall()];c.close()
 for x in r:x['selection_score']=round(x['quality_score']*.35+x['on_time_score']*.3+(100-x['cost_score'])*.2+(100-x['risk_score'])*.15,1)
 r.sort(key=lambda x:x['selection_score'],reverse=True);return {'recommended_suppliers':r,'method':'weighted quality/on-time/cost/risk score'}
@router.post('/plans')
def create_plan(p:PlanIn,x_access_code:str=Header(default='')):
 write_auth(x_access_code);pid='PLAN-'+uuid.uuid4().hex[:8].upper();now=time.time();c=conn();m=live_metrics(c);result=demand_forecast(m,p.horizon_days) if p.plan_type=='demand' else supply_plan(m) if p.plan_type=='supply' else {'capacity':p.capacity,'target_service_level':p.target_service_level,'constraints':p.constraints,'live':{'active_orders':len(m['active_orders']),'low_stock_skus':len(m['low_stock']),'yard_units':m['yard_units']}};c.execute('INSERT INTO supply_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)',(pid,p.plan_type,p.name,p.horizon_days,p.capacity,p.target_service_level,p.constraints,'calculated',json.dumps(result),now,now));c.commit();c.close();return {'id':pid,'status':'calculated','result':result}
@router.get('/plans')
def plans(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();r=[dict(x) for x in c.execute('SELECT * FROM supply_plans ORDER BY created_at DESC LIMIT 100').fetchall()];c.close()
 for x in r:
  try:x['result']=json.loads(x['result'])
  except Exception:pass
 return {'results':r}
@router.get('/production-planning')
def production_planning(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();m=live_metrics(c);c.close();queues={}
 for x in m['active_orders']:queues[x.get('warehouse_id') or 'main']=queues.get(x.get('warehouse_id') or 'main',0)+1
 return {'schedule':[{'warehouse_id':k,'order_load':v,'recommended_wave_count':max(1,(v+9)//10),'priority':'high' if v>20 else 'normal'} for k,v in queues.items()],'materials_risk':m['low_stock'],'capacity_loading':sum(queues.values()),'output_control':'sequence by readiness, stock availability and shipment handoff'}
@router.post('/network-nodes')
def add_node(p:NodeIn,x_access_code:str=Header(default='')):
 write_auth(x_access_code);nid='NODE-'+uuid.uuid4().hex[:8].upper();now=time.time();c=conn();c.execute('INSERT INTO supply_network_nodes VALUES (?,?,?,?,?,?,?,?)',(nid,p.name,p.node_type,p.location,p.capacity,'active',now,now));c.commit();c.close();return {'id':nid,'status':'active'}
@router.get('/network-design')
def network_design(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();nodes=[dict(x) for x in c.execute("SELECT * FROM supply_network_nodes WHERE status='active'").fetchall()];warehouses=rows(c,"SELECT id,name,address FROM warehouses WHERE is_active=1") if exists(c,'warehouses') else [];m=live_metrics(c);c.close();return {'nodes':nodes,'warehouses':warehouses,'fulfillment_model':{'active_order_load':len(m['active_orders']),'warehouse_count':len(warehouses),'recommended_model':'multi-node' if len(warehouses)>1 else 'centralized','capacity_pressure':'high' if len(m['active_orders'])>max(20,len(warehouses)*20) else 'normal'},'channels':['warehouse','yard','transport','customer delivery']}
@router.post('/customer-experience')
def set_customer_metric(p:CustomerMetricIn,x_access_code:str=Header(default='')):
 write_auth(x_access_code);cid='CX-'+uuid.uuid4().hex[:8].upper();c=conn();c.execute('INSERT INTO supply_customer_metrics VALUES (?,?,?,?,?,?,?)',(cid,p.segment,p.availability_pct,p.promise_days,p.cost_to_serve,p.service_quality,time.time()));c.commit();c.close();return {'id':cid}
@router.get('/customer-experience')
def customer_experience(x_access_code:str=Header(default='')):
 read_auth(x_access_code);c=conn();m=live_metrics(c);custom=[dict(x) for x in c.execute('SELECT * FROM supply_customer_metrics ORDER BY updated_at DESC').fetchall()];c.close();availability=max(0,100-len(m['low_stock'])*2);delivery_quality=max(0,100-m['at_risk']*3);return {'live_estimate':{'availability_pct':round(availability,1),'delivery_promise_risk_count':m['at_risk'],'service_quality_pct':round(delivery_quality,1),'cost_to_serve_signal':'elevated' if m['at_risk'] or m['yard_units']>10 else 'normal'},'segments':custom}

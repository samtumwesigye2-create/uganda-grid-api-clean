import os,sqlite3,time
from fastapi import APIRouter,Header
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter(prefix='/visibility',tags=['supply-chain-visibility'])
def conn():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def auth(code):require_permission(code,'shipments:read')
def exists(c,t):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None
def rows(c,q,a=()):
 try:return [dict(x) for x in c.execute(q,a).fetchall()]
 except Exception:return []
@router.get('/summary')
def summary(x_access_code:str=Header(default='')):
 auth(x_access_code);c=conn();ship=rows(c,'SELECT shipment_number,status,delivery_status FROM shipments ORDER BY rowid DESC LIMIT 500') if exists(c,'shipments') else [];orders=rows(c,"SELECT order_number,status,shipment_number,delivery_grid_id,updated_at FROM orders ORDER BY updated_at DESC LIMIT 500") if exists(c,'orders') else [];yard=rows(c,"SELECT id,status,shipment_number,updated_at FROM yard_units ORDER BY updated_at DESC LIMIT 500") if exists(c,'yard_units') else []
 tracked=len(ship);delivered=sum(1 for x in ship if str(x.get('status','')).lower()=='delivered' or str(x.get('delivery_status','')).lower()=='delivered');at_risk=sum(1 for x in ship if str(x.get('status','')).lower() in ('delayed','exception','failed','held') or str(x.get('delivery_status','')).lower() in ('delayed','exception','failed','held'));c.close();return {'tracked_shipments':tracked,'delivered':delivered,'at_risk':at_risk,'active_orders':sum(1 for x in orders if x.get('status') not in ('delivered','cancelled','returned')),'yard_units':sum(1 for x in yard if x.get('status') not in ('departed','cancelled')),'generated_at':time.time()}
@router.get('/network')
def network(q:str='',x_access_code:str=Header(default='')):
 auth(x_access_code);c=conn();ship=rows(c,'SELECT shipment_number,status,delivery_status FROM shipments ORDER BY rowid DESC LIMIT 300') if exists(c,'shipments') else [];orders=rows(c,'SELECT order_number,status,shipment_number,delivery_grid_id,warehouse_id,updated_at FROM orders ORDER BY updated_at DESC LIMIT 300') if exists(c,'orders') else [];yard=rows(c,'SELECT * FROM yard_units ORDER BY updated_at DESC LIMIT 300') if exists(c,'yard_units') else [];c.close();needle=q.lower().strip()
 def keep(x):return not needle or needle in ' '.join(str(v) for v in x.values()).lower()
 return {'shipments':[x for x in ship if keep(x)],'orders':[x for x in orders if keep(x)],'yard':[x for x in yard if keep(x)],'generated_at':time.time()}
@router.get('/trace/{reference}')
def trace(reference:str,x_access_code:str=Header(default='')):
 auth(x_access_code);c=conn();r='%'+reference+'%';ship=rows(c,'SELECT * FROM shipments WHERE shipment_number LIKE ? LIMIT 20',(r,)) if exists(c,'shipments') else [];orders=rows(c,'SELECT * FROM orders WHERE order_number LIKE ? OR shipment_number LIKE ? OR delivery_grid_id LIKE ? LIMIT 20',(r,r,r)) if exists(c,'orders') else [];yard=rows(c,'SELECT * FROM yard_units WHERE shipment_number LIKE ? OR order_number LIKE ? LIMIT 20',(r,r)) if exists(c,'yard_units') else [];c.close();return {'reference':reference,'shipments':ship,'orders':orders,'yard':yard,'generated_at':time.time()}

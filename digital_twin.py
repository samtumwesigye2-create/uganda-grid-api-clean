import os,sqlite3,time
from fastapi import APIRouter,Header
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db')
router=APIRouter(prefix='/digital-twin',tags=['digital-twin'])
def conn():
 c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def access(code):require_permission(code,'shipments:read')
def exists(c,t):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None
def rows(c,sql,args=()):
 try:return [dict(x) for x in c.execute(sql,args).fetchall()]
 except Exception:return []
def n(c,t,where='1=1'):
 if not exists(c,t):return 0
 try:return c.execute(f'SELECT COUNT(*) n FROM {t} WHERE {where}').fetchone()['n']
 except Exception:return 0
@router.get('/snapshot')
def snapshot(x_access_code:str=Header(default='')):
 access(x_access_code);c=conn();start=time.time()
 facilities=rows(c,"SELECT id,name,address,is_active FROM warehouses WHERE is_active=1 ORDER BY name") if exists(c,'warehouses') else []
 orders=rows(c,"SELECT order_number,status,warehouse_id,delivery_grid_id,shipment_number,updated_at FROM orders WHERE status NOT IN ('delivered','cancelled','returned') ORDER BY updated_at DESC LIMIT 100") if exists(c,'orders') else []
 yard=rows(c,"SELECT * FROM yard_units WHERE status NOT IN ('departed','cancelled') ORDER BY updated_at DESC LIMIT 100") if exists(c,'yard_units') else []
 shipments=rows(c,"SELECT shipment_number,status,delivery_status FROM shipments ORDER BY rowid DESC LIMIT 100") if exists(c,'shipments') else []
 vehicles=rows(c,"SELECT * FROM vehicles LIMIT 100") if exists(c,'vehicles') else []
 stock=rows(c,"SELECT product_sku,warehouse_id,quantity_on_hand FROM stock ORDER BY warehouse_id,product_sku LIMIT 500") if exists(c,'stock') else []
 metrics={'facilities':len(facilities),'active_orders':len(orders),'yard_assets':len(yard),'shipments':len(shipments),'vehicles':len(vehicles),'stock_positions':len(stock)}
 c.close();return {'generated_at':time.time(),'sync_ms':round((time.time()-start)*1000,1),'metrics':metrics,'facilities':facilities,'orders':orders,'yard':yard,'shipments':shipments,'vehicles':vehicles,'stock':stock}
@router.get('/facility/{warehouse_id}')
def facility(warehouse_id:str,x_access_code:str=Header(default='')):
 access(x_access_code);c=conn();w=rows(c,'SELECT id,name,address,is_active FROM warehouses WHERE id=?',(warehouse_id,));stock=rows(c,'SELECT product_sku,quantity_on_hand FROM stock WHERE warehouse_id=? ORDER BY product_sku',(warehouse_id,));orders=rows(c,"SELECT order_number,status,subtotal,updated_at FROM orders WHERE warehouse_id=? AND status NOT IN ('delivered','cancelled','returned') ORDER BY updated_at DESC",(warehouse_id,)) if exists(c,'orders') else [];c.close();return {'facility':w[0] if w else {'id':warehouse_id},'stock':stock,'active_orders':orders,'generated_at':time.time()}

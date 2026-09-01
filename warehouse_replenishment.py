import os,sqlite3,time,uuid,math
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_reorder_rules(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',supplier_id TEXT,reorder_point REAL NOT NULL DEFAULT 0,safety_stock REAL NOT NULL DEFAULT 0,target_stock REAL NOT NULL DEFAULT 0,lead_time_days REAL NOT NULL DEFAULT 7,min_order_qty REAL NOT NULL DEFAULT 1,order_multiple REAL NOT NULL DEFAULT 1,enabled INTEGER NOT NULL DEFAULT 1,updated_at REAL NOT NULL,UNIQUE(sku,warehouse_id))''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_purchase_recommendations(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL,supplier_id TEXT,quantity REAL NOT NULL,reason TEXT,status TEXT NOT NULL DEFAULT 'open',created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_reorder_rules ON warehouse_reorder_rules(warehouse_id,enabled)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def available(c,sku,w):
 s=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();on=float(s['quantity_on_hand']) if s else 0
 r=c.execute("SELECT COALESCE(SUM(l.reserved_qty-l.picked_qty),0) q FROM warehouse_order_lines l JOIN warehouse_customer_orders o ON o.id=l.order_id WHERE l.sku=? AND o.warehouse_id=? AND o.status NOT IN ('cancelled','dispatched')",(sku,w)).fetchone();return on-float(r['q'] or 0)
def inbound(c,sku,w):
 try:r=c.execute("SELECT COALESCE(SUM(l.quantity-l.received_qty),0) q FROM warehouse_po_lines l JOIN warehouse_purchase_orders p ON p.id=l.po_id WHERE l.sku=? AND p.warehouse_id=? AND p.status NOT IN ('closed','cancelled')",(sku,w)).fetchone();return float(r['q'] or 0)
 except:return 0
def demand(c,sku,w,days=30):
 since=time.time()-days*86400
 try:r=c.execute("SELECT COALESCE(SUM(l.dispatched_qty),0) q FROM warehouse_order_lines l JOIN warehouse_customer_orders o ON o.id=l.order_id WHERE l.sku=? AND o.warehouse_id=? AND o.updated_at>=?",(sku,w,since)).fetchone();return float(r['q'] or 0)/days
 except:return 0
@router.post('/warehouse/replenishment/rules')
def rule(sku:str=Form(...),warehouse_id:str=Form('main'),supplier_id:str=Form(''),reorder_point:float=Form(0),safety_stock:float=Form(0),target_stock:float=Form(0),lead_time_days:float=Form(7),min_order_qty:float=Form(1),order_multiple:float=Form(1),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');sku=sku.strip();c=db();old=c.execute('SELECT id FROM warehouse_reorder_rules WHERE sku=? AND warehouse_id=?',(sku,warehouse_id)).fetchone();i=old['id'] if old else str(uuid.uuid4());target=max(target_stock,reorder_point+safety_stock);c.execute('''INSERT INTO warehouse_reorder_rules(id,sku,warehouse_id,supplier_id,reorder_point,safety_stock,target_stock,lead_time_days,min_order_qty,order_multiple,enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?) ON CONFLICT(sku,warehouse_id) DO UPDATE SET supplier_id=excluded.supplier_id,reorder_point=excluded.reorder_point,safety_stock=excluded.safety_stock,target_stock=excluded.target_stock,lead_time_days=excluded.lead_time_days,min_order_qty=excluded.min_order_qty,order_multiple=excluded.order_multiple,enabled=1,updated_at=excluded.updated_at''',(i,sku,warehouse_id,supplier_id or None,reorder_point,safety_stock,target,lead_time_days,min_order_qty,max(order_multiple,1),time.time()));c.commit();r=dict(c.execute('SELECT * FROM warehouse_reorder_rules WHERE sku=? AND warehouse_id=?',(sku,warehouse_id)).fetchone());c.close();return r
@router.get('/warehouse/replenishment')
def analyze(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE warehouse_id=? AND enabled=1 ORDER BY sku',(warehouse_id,)).fetchall();out=[]
 for r in rules:
  av=available(c,r['sku'],warehouse_id);inc=inbound(c,r['sku'],warehouse_id);daily=demand(c,r['sku'],warehouse_id);projected=av+inc-(daily*float(r['lead_time_days']));trigger=projected<=float(r['reorder_point'])
  need=max(0,float(r['target_stock'])-(av+inc));mult=max(float(r['order_multiple']),1);suggest=max(float(r['min_order_qty']),math.ceil(need/mult)*mult) if trigger else 0
  out.append({'sku':r['sku'],'supplier_id':r['supplier_id'],'on_hand_available':round(av,2),'inbound':round(inc,2),'daily_demand':round(daily,2),'lead_time_days':r['lead_time_days'],'projected_at_replenishment':round(projected,2),'reorder_point':r['reorder_point'],'safety_stock':r['safety_stock'],'target_stock':r['target_stock'],'reorder_required':trigger,'recommended_qty':suggest})
 c.close();return {'warehouse_id':warehouse_id,'recommendations':out,'required':sum(1 for x in out if x['reorder_required'])}
@router.post('/warehouse/replenishment/generate')
def generate(warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE warehouse_id=? AND enabled=1',(warehouse_id,)).fetchall();created=[]
 for r in rules:
  av=available(c,r['sku'],warehouse_id);inc=inbound(c,r['sku'],warehouse_id);daily=demand(c,r['sku'],warehouse_id);projected=av+inc-daily*float(r['lead_time_days'])
  if projected>float(r['reorder_point']):continue
  need=max(0,float(r['target_stock'])-(av+inc));mult=max(float(r['order_multiple']),1);qty=max(float(r['min_order_qty']),math.ceil(need/mult)*mult)
  existing=c.execute("SELECT id FROM warehouse_purchase_recommendations WHERE sku=? AND warehouse_id=? AND status='open'",(r['sku'],warehouse_id)).fetchone()
  if existing:continue
  i=str(uuid.uuid4());now=time.time();reason=f'Projected stock {round(projected,2)} <= reorder point {r["reorder_point"]}';c.execute('INSERT INTO warehouse_purchase_recommendations VALUES(?,?,?,?,?,?,?,?,?)',(i,r['sku'],warehouse_id,r['supplier_id'],qty,reason,'open',now,now));created.append({'id':i,'sku':r['sku'],'quantity':qty,'reason':reason})
 c.commit();c.close();return {'created':len(created),'recommendations':created}
@router.get('/warehouse/replenishment/purchase-recommendations')
def purchases(warehouse_id:str=Query('main'),status:str=Query('open'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute('SELECT * FROM warehouse_purchase_recommendations WHERE warehouse_id=? AND status=? ORDER BY created_at DESC',(warehouse_id,status)).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/replenishment/purchase-recommendations/{recommendation_id}/status')
def rec_status(recommendation_id:str,status:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if status not in {'approved','ordered','dismissed','open'}:raise HTTPException(400,'Invalid recommendation status')
 c=db();c.execute('UPDATE warehouse_purchase_recommendations SET status=?,updated_at=? WHERE id=?',(status,time.time(),recommendation_id));c.commit();c.close();return {'id':recommendation_id,'status':status}

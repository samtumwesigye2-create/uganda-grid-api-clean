import os,sqlite3,time,uuid,math
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_reorder_rules(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',supplier_id TEXT,reorder_point REAL NOT NULL DEFAULT 0,safety_stock REAL NOT NULL DEFAULT 0,target_stock REAL NOT NULL DEFAULT 0,lead_time_days REAL NOT NULL DEFAULT 7,min_order_qty REAL NOT NULL DEFAULT 1,order_multiple REAL NOT NULL DEFAULT 1,enabled INTEGER NOT NULL DEFAULT 1,updated_at REAL NOT NULL,UNIQUE(sku,warehouse_id))''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_purchase_recommendations(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL,supplier_id TEXT,quantity REAL NOT NULL,reason TEXT,status TEXT NOT NULL DEFAULT 'open',created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_reorder_rules ON warehouse_reorder_rules(warehouse_id,enabled)');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def table(c,n):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def scalar(c,q,a=()):
 try:r=c.execute(q,a).fetchone();return float(r['q'] or 0) if r else 0
 except sqlite3.Error:return 0
def on_hand(c,sku,w):return scalar(c,'SELECT COALESCE(quantity_on_hand,0) q FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w))
def customer_allocated(c,sku,w):
 if not table(c,'warehouse_lot_reservations'):return 0
 return scalar(c,"SELECT COALESCE(SUM(quantity),0) q FROM warehouse_lot_reservations WHERE sku=? AND warehouse_id=? AND status IN ('allocated','picked','recall_blocked')",(sku,w))
def legacy_allocated(c,sku,w):
 if not table(c,'warehouse_legacy_pick_reservations'):return 0
 return scalar(c,"SELECT COALESCE(SUM(quantity),0) q FROM warehouse_legacy_pick_reservations WHERE sku=? AND warehouse_id=? AND status='picked'",(sku,w))
def transfer_reserved(c,sku,w):
 if not table(c,'warehouse_transfer_lots') or not table(c,'warehouse_transfer_orders'):return 0
 return scalar(c,"SELECT COALESCE(SUM(z.quantity),0) q FROM warehouse_transfer_lots z JOIN warehouse_transfer_orders t ON t.id=z.transfer_id WHERE z.sku=? AND t.from_warehouse=? AND z.status='reserved'",(sku,w))
def quality_held(c,sku,w):
 if not table(c,'warehouse_quality_hold_lots'):return 0
 return scalar(c,"SELECT COALESCE(SUM(q.quantity),0) q FROM warehouse_quality_hold_lots q JOIN warehouse_quality_holds h ON h.id=q.hold_id WHERE h.sku=? AND h.warehouse_id=? AND q.status='held'",(sku,w))
def available(c,sku,w):return max(0,on_hand(c,sku,w)-customer_allocated(c,sku,w)-legacy_allocated(c,sku,w)-transfer_reserved(c,sku,w)-quality_held(c,sku,w))
def po_inbound(c,sku,w):
 if not table(c,'warehouse_po_lines'):return 0
 return scalar(c,"SELECT COALESCE(SUM(l.ordered_qty-l.received_qty),0) q FROM warehouse_po_lines l JOIN warehouse_purchase_orders p ON p.id=l.po_id WHERE l.sku=? AND p.warehouse_id=? AND p.status IN ('open','partial')",(sku,w))
def transfer_inbound(c,sku,w):
 if not table(c,'warehouse_transfer_lots'):return 0
 return scalar(c,"SELECT COALESCE(SUM(z.quantity),0) q FROM warehouse_transfer_lots z JOIN warehouse_transfer_orders t ON t.id=z.transfer_id WHERE z.sku=? AND t.to_warehouse=? AND z.status='in_transit'",(sku,w))
def inbound(c,sku,w):return po_inbound(c,sku,w)+transfer_inbound(c,sku,w)
def demand(c,sku,w,days=30):
 since=time.time()-days*86400
 if table(c,'warehouse_dispatch_ledger') and table(c,'warehouse_lot_reservations'):
  return scalar(c,"SELECT COALESCE(SUM(r.quantity),0) q FROM warehouse_lot_reservations r JOIN warehouse_dispatch_ledger d ON d.order_id=r.order_id WHERE r.sku=? AND r.warehouse_id=? AND r.status='dispatched' AND d.created_at>=?",(sku,w,since))/days
 if table(c,'warehouse_operations'):
  return scalar(c,"SELECT COALESCE(SUM(quantity),0) q FROM warehouse_operations WHERE sku=? AND warehouse_id=? AND operation_type='dispatch' AND action_code='dispatch' AND created_at>=?",(sku,w,since))/days
 return 0
def calc(c,r):
 sku=r['sku'];w=r['warehouse_id'];oh=on_hand(c,sku,w);cust=customer_allocated(c,sku,w);legacy=legacy_allocated(c,sku,w);tr=transfer_reserved(c,sku,w);qh=quality_held(c,sku,w);av=max(0,oh-cust-legacy-tr-qh);po=po_inbound(c,sku,w);tin=transfer_inbound(c,sku,w);inc=po+tin;daily=demand(c,sku,w);lead=float(r['lead_time_days']);projected=av+inc-daily*lead;trigger=projected<=float(r['reorder_point']);need=max(0,float(r['target_stock'])-(av+inc));mult=max(float(r['order_multiple']),1);suggest=max(float(r['min_order_qty']),math.ceil(need/mult)*mult) if trigger and need>0 else 0
 return {'sku':sku,'supplier_id':r['supplier_id'],'on_hand':round(oh,2),'customer_allocated':round(cust,2),'legacy_picked':round(legacy,2),'transfer_reserved':round(tr,2),'quality_held':round(qh,2),'available_to_promise':round(av,2),'po_inbound':round(po,2),'transfer_inbound':round(tin,2),'inbound_total':round(inc,2),'daily_dispatch_demand':round(daily,2),'lead_time_days':lead,'projected_at_replenishment':round(projected,2),'reorder_point':r['reorder_point'],'safety_stock':r['safety_stock'],'target_stock':r['target_stock'],'reorder_required':trigger,'recommended_qty':suggest}
@router.post('/warehouse/replenishment/rules')
def rule(sku:str=Form(...),warehouse_id:str=Form('main'),supplier_id:str=Form(''),reorder_point:float=Form(0),safety_stock:float=Form(0),target_stock:float=Form(0),lead_time_days:float=Form(7),min_order_qty:float=Form(1),order_multiple:float=Form(1),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');sku=sku.strip();c=db();c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT id FROM warehouse_reorder_rules WHERE sku=? AND warehouse_id=?',(sku,warehouse_id)).fetchone();i=old['id'] if old else str(uuid.uuid4());target=max(target_stock,reorder_point+safety_stock);c.execute('''INSERT INTO warehouse_reorder_rules(id,sku,warehouse_id,supplier_id,reorder_point,safety_stock,target_stock,lead_time_days,min_order_qty,order_multiple,enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?) ON CONFLICT(sku,warehouse_id) DO UPDATE SET supplier_id=excluded.supplier_id,reorder_point=excluded.reorder_point,safety_stock=excluded.safety_stock,target_stock=excluded.target_stock,lead_time_days=excluded.lead_time_days,min_order_qty=excluded.min_order_qty,order_multiple=excluded.order_multiple,enabled=1,updated_at=excluded.updated_at''',(i,sku,warehouse_id,supplier_id or None,reorder_point,safety_stock,target,lead_time_days,min_order_qty,max(order_multiple,1),time.time()));c.execute('COMMIT');r=dict(c.execute('SELECT * FROM warehouse_reorder_rules WHERE sku=? AND warehouse_id=?',(sku,warehouse_id)).fetchone());c.close();return r
@router.get('/warehouse/replenishment')
def analyze(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE warehouse_id=? AND enabled=1 ORDER BY sku',(warehouse_id,)).fetchall();out=[calc(c,r) for r in rules];c.close();return {'warehouse_id':warehouse_id,'recommendations':out,'required':sum(1 for x in out if x['reorder_required'])}
@router.post('/warehouse/replenishment/generate')
def generate(warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE');rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE warehouse_id=? AND enabled=1',(warehouse_id,)).fetchall();created=[];updated=[]
 try:
  for r in rules:
   z=calc(c,r)
   if not z['reorder_required'] or z['recommended_qty']<=0:continue
   qty=float(z['recommended_qty']);reason=f"ATP {z['available_to_promise']} + inbound {z['inbound_total']} - lead-time demand {round(z['daily_dispatch_demand']*z['lead_time_days'],2)} = projected {z['projected_at_replenishment']} <= reorder point {z['reorder_point']}";existing=c.execute("SELECT * FROM warehouse_purchase_recommendations WHERE sku=? AND warehouse_id=? AND status='open'",(r['sku'],warehouse_id)).fetchone();now=time.time()
   if existing:c.execute('UPDATE warehouse_purchase_recommendations SET supplier_id=?,quantity=?,reason=?,updated_at=? WHERE id=?',(r['supplier_id'],qty,reason,now,existing['id']));updated.append({'id':existing['id'],'sku':r['sku'],'quantity':qty,'reason':reason})
   else:
    i=str(uuid.uuid4());c.execute('INSERT INTO warehouse_purchase_recommendations VALUES(?,?,?,?,?,?,?,?,?)',(i,r['sku'],warehouse_id,r['supplier_id'],qty,reason,'open',now,now));created.append({'id':i,'sku':r['sku'],'quantity':qty,'reason':reason})
  c.execute('COMMIT');return {'created':len(created),'updated':len(updated),'recommendations':created+updated}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/replenishment/purchase-recommendations')
def purchases(warehouse_id:str=Query('main'),status:str=Query('open'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute('SELECT * FROM warehouse_purchase_recommendations WHERE warehouse_id=? AND status=? ORDER BY updated_at DESC',(warehouse_id,status)).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/replenishment/purchase-recommendations/{recommendation_id}/status')
def rec_status(recommendation_id:str,status:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if status not in {'approved','ordered','dismissed','open'}:raise HTTPException(400,'Invalid recommendation status')
 c=db();c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT id FROM warehouse_purchase_recommendations WHERE id=?',(recommendation_id,)).fetchone()
 if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Recommendation not found')
 c.execute('UPDATE warehouse_purchase_recommendations SET status=?,updated_at=? WHERE id=?',(status,time.time(),recommendation_id));c.execute('COMMIT');c.close();return {'id':recommendation_id,'status':status}

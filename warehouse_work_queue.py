import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def auth(k,p):require_permission(k,p)
def taskno():return f'TASK-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def table(c,n):return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def add(c,w,t,title,ref,qty=0,priority=100,note=''):
 old=c.execute("SELECT id FROM warehouse_tasks WHERE warehouse_id=? AND task_type=? AND reference_no=? AND status IN ('assigned','in_progress','blocked')",(w,t,ref)).fetchone()
 if old:return False
 c.execute('INSERT INTO warehouse_tasks(id,task_no,task_type,title,staff_id,warehouse_id,reference_no,priority,status,quantity,created_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),taskno(),t,title,None,w,ref,priority,'assigned',float(qty or 0),time.time(),note));return True
def sync(c,w):
 made=0
 if table(c,'warehouse_purchase_orders') and table(c,'warehouse_po_lines'):
  for r in c.execute("SELECT p.id,p.po_number,p.status,COALESCE(SUM(l.ordered_qty-l.received_qty),0) qty FROM warehouse_purchase_orders p JOIN warehouse_po_lines l ON l.po_id=p.id WHERE p.warehouse_id=? AND p.status IN ('open','partial') GROUP BY p.id,p.po_number,p.status HAVING qty>0",(w,)).fetchall():made+=add(c,w,'receiving','Receive purchase order '+r['po_number'],r['po_number'],r['qty'],40,'Generated from outstanding PO quantity')
 if table(c,'warehouse_lots'):
  for r in c.execute("SELECT sku,COALESCE(lot_no,batch_no,id) ref,quantity_available FROM warehouse_lots WHERE warehouse_id=? AND quantity_available>0 AND (location_code IS NULL OR location_code='') AND status='available'",(w,)).fetchall():made+=add(c,w,'putaway','Put away '+r['sku'],'LOT:'+str(r['ref']),r['quantity_available'],50,'Generated from received inventory without a storage location')
 if table(c,'warehouse_pick_waves'):
  for r in c.execute("SELECT w.wave_no,COALESCE(SUM(l.quantity),0) qty FROM warehouse_pick_waves w JOIN warehouse_wave_lines l ON l.wave_id=w.id WHERE w.warehouse_id=? AND w.status='open' AND l.status='allocated' GROUP BY w.id,w.wave_no",(w,)).fetchall():made+=add(c,w,'picking','Pick wave '+r['wave_no'],r['wave_no'],r['qty'],30,'Generated from allocated outbound pick wave')
 if table(c,'warehouse_customer_orders'):
  for r in c.execute("SELECT id,order_no,status FROM warehouse_customer_orders WHERE warehouse_id=? AND status IN ('picked','packed')",(w,)).fetchall():
   if r['status']=='picked':made+=add(c,w,'packing','Pack order '+r['order_no'],r['order_no'],0,35,'Generated after picking completed')
   else:made+=add(c,w,'dispatch','Prepare dispatch '+r['order_no'],r['order_no'],0,20,'Generated from packed order awaiting approved dispatch')
 if table(c,'warehouse_transfer_orders'):
  for r in c.execute("SELECT transfer_no,status FROM warehouse_transfer_orders WHERE (from_warehouse=? OR to_warehouse=?) AND status IN ('draft','in_transit')",(w,w)).fetchall():
   title=('Prepare transfer shipment ' if r['status']=='draft' else 'Receive transfer ')+r['transfer_no'];made+=add(c,w,'transfer',title,r['transfer_no'],0,45,'Generated from inter-warehouse transfer state')
 if table(c,'warehouse_quality_holds'):
  for r in c.execute("SELECT hold_no,sku,quantity FROM warehouse_quality_holds WHERE warehouse_id=? AND status='quarantine'",(w,)).fetchall():made+=add(c,w,'quality','Inspect quarantined '+r['sku'],r['hold_no'],r['quantity'],10,'Generated from active quality hold')
 if table(c,'warehouse_purchase_recommendations'):
  for r in c.execute("SELECT id,sku,quantity FROM warehouse_purchase_recommendations WHERE warehouse_id=? AND status='approved'",(w,)).fetchall():made+=add(c,w,'replenishment','Place replenishment order for '+r['sku'],'REPL:'+r['id'],r['quantity'],60,'Generated from approved replenishment recommendation')
 return made
@router.post('/warehouse/work-queue/sync')
def synchronize(warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:n=sync(c,warehouse_id);c.execute('COMMIT');return {'warehouse_id':warehouse_id,'tasks_created':n,'idempotent':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/work-queue')
def queue(warehouse_id:str=Query('main'),auto_sync:bool=Query(True),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db()
 if auto_sync:
  c.execute('BEGIN IMMEDIATE')
  try:sync(c,warehouse_id);c.execute('COMMIT')
  except Exception:c.execute('ROLLBACK');c.close();raise
 rows=[dict(x) for x in c.execute("SELECT t.*,s.name staff_name,s.role staff_role FROM warehouse_tasks t LEFT JOIN warehouse_staff s ON s.id=t.staff_id WHERE t.warehouse_id=? AND t.status IN ('assigned','in_progress','blocked') ORDER BY t.priority,t.created_at",(warehouse_id,)).fetchall()];c.close();return {'warehouse_id':warehouse_id,'count':len(rows),'results':rows}

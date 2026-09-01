import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_quality_holds(id TEXT PRIMARY KEY,hold_no TEXT UNIQUE NOT NULL,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL,lot_no TEXT,batch_no TEXT,quantity REAL NOT NULL DEFAULT 0,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'quarantine',quarantine_location TEXT,inspection_result TEXT,authorized_by TEXT,created_at REAL NOT NULL,resolved_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_quality_hold_lots(id TEXT PRIMARY KEY,hold_id TEXT NOT NULL,lot_id TEXT NOT NULL,quantity REAL NOT NULL,status TEXT NOT NULL DEFAULT 'held',created_at REAL NOT NULL,resolved_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_recalls(id TEXT PRIMARY KEY,recall_no TEXT UNIQUE NOT NULL,title TEXT NOT NULL,sku TEXT NOT NULL,lot_no TEXT,batch_no TEXT,reason TEXT NOT NULL,severity TEXT NOT NULL DEFAULT 'high',status TEXT NOT NULL DEFAULT 'open',created_at REAL NOT NULL,closed_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_recall_actions(id TEXT PRIMARY KEY,recall_id TEXT NOT NULL,action_type TEXT NOT NULL,reference_no TEXT,customer_name TEXT,quantity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'identified',note TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_qhold ON warehouse_quality_holds(warehouse_id,status,sku,lot_no)');c.execute('CREATE INDEX IF NOT EXISTS idx_qhold_lot ON warehouse_quality_hold_lots(lot_id,status)');c.execute('CREATE INDEX IF NOT EXISTS idx_recall ON warehouse_recalls(status,sku,lot_no)');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def num(prefix):return f'{prefix}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def stock_change(c,sku,w,q):
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();old=float(r['quantity_on_hand']) if r else 0;new=old+q
 if new<0:raise HTTPException(409,'Aggregate inventory conflict')
 if r:c.execute('UPDATE stock SET quantity_on_hand=? WHERE product_sku=? AND warehouse_id=?',(new,sku,w))
 else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,w,new))
def lot_matches(c,sku,w,lot,batch):
 q="SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND quantity_available>0 AND status IN ('available','quarantine','recall_hold')";a=[sku,w]
 if lot:q+=' AND lot_no=?';a.append(lot)
 if batch:q+=' AND batch_no=?';a.append(batch)
 return c.execute(q,a).fetchall()
def held(c,lot_id):return float(c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_quality_hold_lots WHERE lot_id=? AND status='held'",(lot_id,)).fetchone()['q'] or 0)
def reserved(c,lot_id):
 a=float(c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_lot_reservations WHERE lot_id=? AND status IN ('allocated','picked')",(lot_id,)).fetchone()['q'] or 0);b=float(c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_transfer_lots WHERE source_lot_id=? AND status='reserved'",(lot_id,)).fetchone()['q'] or 0);return a+b
def set_lot_status(c,lot_id):
 lot=c.execute('SELECT quantity_available FROM warehouse_lots WHERE id=?',(lot_id,)).fetchone()
 if not lot:return
 recall=c.execute("SELECT 1 FROM warehouse_recalls r JOIN warehouse_lots l ON l.id=? WHERE r.status='open' AND r.sku=l.sku AND ((r.lot_no!='' AND r.lot_no=l.lot_no) OR (r.batch_no!='' AND r.batch_no=l.batch_no)) LIMIT 1",(lot_id,)).fetchone();st='recall_hold' if recall else ('quarantine' if held(c,lot_id)>0 else ('depleted' if float(lot['quantity_available'])<=0 else 'available'));c.execute('UPDATE warehouse_lots SET status=?,updated_at=? WHERE id=?',(st,time.time(),lot_id))
@router.post('/warehouse/quality/holds')
def hold(sku:str=Form(...),warehouse_id:str=Form('main'),lot_no:str=Form(''),batch_no:str=Form(''),quantity:float=Form(0),reason:str=Form(...),quarantine_location:str=Form('QUARANTINE'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  lots=lot_matches(c,sku,warehouse_id,lot_no,batch_no)
  if not lots:raise HTTPException(404,'Matching available lot inventory not found')
  total=sum(max(0,float(l['quantity_available'])-held(c,l['id'])-reserved(c,l['id'])) for l in lots);qty=quantity if quantity>0 else total
  if qty<=0 or qty>total:raise HTTPException(409,f'Only {total} unreserved units are available to quarantine')
  i=str(uuid.uuid4());n=num('QH');now=time.time();c.execute('INSERT INTO warehouse_quality_holds(id,hold_no,sku,warehouse_id,lot_no,batch_no,quantity,reason,status,quarantine_location,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,n,sku,warehouse_id,lot_no,batch_no,qty,reason,'quarantine',quarantine_location,now));need=qty
  for l in lots:
   if need<=0:break
   free=max(0,float(l['quantity_available'])-held(c,l['id'])-reserved(c,l['id']));take=min(need,free)
   if take>0:c.execute('INSERT INTO warehouse_quality_hold_lots VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),i,l['id'],take,'held',now,None));c.execute("UPDATE warehouse_lots SET status='quarantine',updated_at=? WHERE id=?",(now,l['id']));need-=take
  c.execute('COMMIT');return {'id':i,'hold_no':n,'status':'quarantine','quantity_held':qty}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/quality/holds')
def holds(warehouse_id:str=Query('main'),status:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_quality_holds WHERE warehouse_id=?';a=[warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY created_at DESC';r=[dict(x) for x in c.execute(q,a).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/quality/holds/{hold_id}/resolve')
def resolve(hold_id:str,decision:str=Form(...),inspection_result:str=Form(''),authorized_by:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if decision not in {'release','reject','destroy','return_supplier'}:raise HTTPException(400,'Invalid quality decision')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  h=c.execute('SELECT * FROM warehouse_quality_holds WHERE id=?',(hold_id,)).fetchone()
  if not h:raise HTTPException(404,'Quality hold not found')
  if h['status']!='quarantine':raise HTTPException(400,'Hold already resolved')
  parts=c.execute("SELECT q.*,l.location_code,l.quantity_available FROM warehouse_quality_hold_lots q JOIN warehouse_lots l ON l.id=q.lot_id WHERE q.hold_id=? AND q.status='held'",(hold_id,)).fetchall();qty=sum(float(p['quantity']) for p in parts)
  if decision in {'destroy','return_supplier'}:
   if stock_change(c,h['sku'],h['warehouse_id'],-qty) is False:raise HTTPException(409,'Stock update failed')
   for p in parts:
    q=float(p['quantity'])
    if float(p['quantity_available'])<q:raise HTTPException(409,'Held lot quantity no longer exists')
    c.execute('UPDATE warehouse_lots SET quantity_available=quantity_available-?,updated_at=? WHERE id=?',(q,time.time(),p['lot_id']))
    if p['location_code']:c.execute('UPDATE warehouse_locations SET used_capacity=MAX(0,used_capacity-?),updated_at=? WHERE warehouse_id=? AND location_code=?',(q,time.time(),h['warehouse_id'],p['location_code']))
  status={'release':'released','reject':'rejected','destroy':'destroyed','return_supplier':'return_supplier'}[decision];now=time.time();c.execute('UPDATE warehouse_quality_holds SET status=?,inspection_result=?,authorized_by=?,resolved_at=? WHERE id=?',(status,inspection_result,authorized_by,now,hold_id));c.execute("UPDATE warehouse_quality_hold_lots SET status=?,resolved_at=? WHERE hold_id=? AND status='held'",(status,now,hold_id))
  for p in parts:set_lot_status(c,p['lot_id'])
  c.execute('COMMIT');return {'id':hold_id,'status':status,'quantity':qty,'stock_removed':decision in {'destroy','return_supplier'}}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/recalls')
def recall(title:str=Form(...),sku:str=Form(...),lot_no:str=Form(''),batch_no:str=Form(''),reason:str=Form(...),severity:str=Form('high'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if not lot_no and not batch_no:raise HTTPException(400,'Recall requires lot number or batch number')
 if severity not in {'low','medium','high','critical'}:raise HTTPException(400,'Invalid recall severity')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  i=str(uuid.uuid4());n=num('RCL');now=time.time();c.execute('INSERT INTO warehouse_recalls VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,n,title,sku,lot_no,batch_no,reason,severity,'open',now,None));q="SELECT * FROM warehouse_lots WHERE sku=?";a=[sku]
  if lot_no:q+=' AND lot_no=?';a.append(lot_no)
  if batch_no:q+=' AND batch_no=?';a.append(batch_no)
  lots=c.execute(q,a).fetchall()
  for l in lots:
   c.execute("UPDATE warehouse_lots SET status='recall_hold',updated_at=? WHERE id=?",(now,l['id']));c.execute("UPDATE warehouse_lot_reservations SET status='recall_blocked',updated_at=? WHERE lot_id=? AND status IN ('allocated','picked')",(now,l['id']));c.execute("UPDATE warehouse_transfer_lots SET status='recall_blocked' WHERE source_lot_id=? AND status='reserved'",(l['id'],))
  rows=c.execute('''SELECT DISTINCT o.order_no,o.customer_name,SUM(r.quantity) quantity FROM warehouse_lot_reservations r JOIN warehouse_customer_orders o ON o.id=r.order_id JOIN warehouse_lots l ON l.id=r.lot_id WHERE r.sku=? AND r.status IN ('dispatched','recall_blocked') AND (?='' OR l.lot_no=?) AND (?='' OR l.batch_no=?) GROUP BY o.order_no,o.customer_name''',(sku,lot_no,lot_no,batch_no,batch_no)).fetchall()
  for r in rows:c.execute('INSERT INTO warehouse_recall_actions VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),i,'customer_order',r['order_no'],r['customer_name'],r['quantity'],'identified','Affected lot-linked customer order',now,now))
  c.execute('COMMIT');return {'id':i,'recall_no':n,'affected_orders':len(rows),'affected_lots':len(lots),'status':'open','dispatch_blocked':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/recalls')
def recalls(status:str=Query('open'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rs=[dict(x) for x in c.execute('SELECT * FROM warehouse_recalls WHERE status=? ORDER BY created_at DESC',(status,)).fetchall()]
 for r in rs:r['actions']=[dict(x) for x in c.execute('SELECT * FROM warehouse_recall_actions WHERE recall_id=? ORDER BY created_at',(r['id'],)).fetchall()]
 c.close();return {'results':rs}
@router.post('/warehouse/recalls/{recall_id}/actions/{action_id}')
def action(recall_id:str,action_id:str,status:str=Form(...),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if status not in {'identified','notified','return_requested','returned','closed'}:raise HTTPException(400,'Invalid recall action status')
 c=db();c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT id FROM warehouse_recall_actions WHERE id=? AND recall_id=?',(action_id,recall_id)).fetchone()
 if not r:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Recall action not found')
 c.execute('UPDATE warehouse_recall_actions SET status=?,note=?,updated_at=? WHERE id=?',(status,note,time.time(),action_id));c.execute('COMMIT');c.close();return {'id':action_id,'status':status}
@router.post('/warehouse/recalls/{recall_id}/close')
def close(recall_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  r=c.execute('SELECT * FROM warehouse_recalls WHERE id=?',(recall_id,)).fetchone()
  if not r:raise HTTPException(404,'Recall not found')
  open_actions=c.execute("SELECT COUNT(*) n FROM warehouse_recall_actions WHERE recall_id=? AND status NOT IN ('returned','closed')",(recall_id,)).fetchone()['n']
  if open_actions:raise HTTPException(400,f'{open_actions} recall actions remain open')
  now=time.time();c.execute("UPDATE warehouse_recalls SET status='closed',closed_at=? WHERE id=?",(now,recall_id));q="SELECT id FROM warehouse_lots WHERE sku=?";a=[r['sku']]
  if r['lot_no']:q+=' AND lot_no=?';a.append(r['lot_no'])
  if r['batch_no']:q+=' AND batch_no=?';a.append(r['batch_no'])
  for l in c.execute(q,a).fetchall():set_lot_status(c,l['id'])
  c.execute('COMMIT');return {'id':recall_id,'status':'closed','lot_holds_recalculated':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()

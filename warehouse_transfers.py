import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
from warehouse_approvals import consume_approval
from warehouse_traceability import emit
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfer_orders(id TEXT PRIMARY KEY,transfer_no TEXT UNIQUE NOT NULL,from_warehouse TEXT NOT NULL,to_warehouse TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',notes TEXT,created_at REAL NOT NULL,shipped_at REAL,received_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfer_lines(id TEXT PRIMARY KEY,transfer_id TEXT NOT NULL,sku TEXT NOT NULL,requested_qty REAL NOT NULL,shipped_qty REAL NOT NULL DEFAULT 0,received_qty REAL NOT NULL DEFAULT 0)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfer_lots(id TEXT PRIMARY KEY,transfer_id TEXT NOT NULL,transfer_line_id TEXT NOT NULL,source_lot_id TEXT NOT NULL,sku TEXT NOT NULL,lot_no TEXT,batch_no TEXT,manufacture_date TEXT,expiry_date TEXT,source_location TEXT,quantity REAL NOT NULL,status TEXT NOT NULL DEFAULT 'reserved',destination_lot_id TEXT,destination_location TEXT,created_at REAL NOT NULL,shipped_at REAL,received_at REAL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_transfer_status ON warehouse_transfer_orders(status,from_warehouse,to_warehouse)');c.execute('CREATE INDEX IF NOT EXISTS idx_transfer_lot_source ON warehouse_transfer_lots(source_lot_id,status)');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def no():return f'TRF-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def stock(c,sku,w):
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();return float(r['quantity_on_hand']) if r else 0
def change(c,sku,w,q):
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();new=(float(r['quantity_on_hand']) if r else 0)+q
 if new<0:raise HTTPException(409,f'Insufficient stock for {sku}')
 if r:c.execute('UPDATE stock SET quantity_on_hand=? WHERE product_sku=? AND warehouse_id=?',(new,sku,w))
 else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,w,new))
def free_lot(c,lot):
 r=c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_transfer_lots WHERE source_lot_id=? AND status='reserved'",(lot['id'],)).fetchone();o=c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_lot_reservations WHERE lot_id=? AND status IN ('allocated','picked')",(lot['id'],)).fetchone();return max(0,float(lot['quantity_available'])-float(r['q'] or 0)-float(o['q'] or 0))
def reserve_line(c,t,line,transfer_no):
 need=float(line['requested_qty']);order="CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END,expiry_date,received_at";lots=c.execute(f"SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available' AND quantity_available>0 ORDER BY {order}",(line['sku'],t['from_warehouse'])).fetchall()
 for lot in lots:
  if need<=0:break
  take=min(need,free_lot(c,lot))
  if take<=0:continue
  zid=str(uuid.uuid4());ts=time.time();c.execute('INSERT INTO warehouse_transfer_lots(id,transfer_id,transfer_line_id,source_lot_id,sku,lot_no,batch_no,manufacture_date,expiry_date,source_location,quantity,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(zid,t['id'],line['id'],lot['id'],line['sku'],lot['lot_no'],lot['batch_no'],lot['manufacture_date'],lot['expiry_date'],lot['location_code'],take,'reserved',ts));emit(c,'transfer-reserve:'+zid,line['sku'],'transfer_reserved',t['from_warehouse'],take,lot['lot_no'],lot['batch_no'],'',lot['location_code'],'','transfer',transfer_no,'system','Inventory reserved for inter-warehouse transfer',ts);need-=take
 if need>0:raise HTTPException(409,f'Insufficient unreserved lot stock for {line["sku"]}')
def destination(c,w,qty):return c.execute("SELECT * FROM warehouse_locations WHERE warehouse_id=? AND status='available' AND capacity-used_capacity>=? ORDER BY priority,used_capacity LIMIT 1",(w,qty)).fetchone()
@router.post('/warehouse/transfers')
def create(from_warehouse:str=Form(...),to_warehouse:str=Form(...),lines_json:str=Form('[]'),notes:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if from_warehouse==to_warehouse:raise HTTPException(400,'Source and destination warehouses must differ')
 try:lines=json.loads(lines_json)
 except:raise HTTPException(400,'Invalid transfer lines')
 if not lines:raise HTTPException(400,'Transfer requires at least one line')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  i=str(uuid.uuid4());n=no();now=time.time();c.execute('INSERT INTO warehouse_transfer_orders(id,transfer_no,from_warehouse,to_warehouse,status,notes,created_at) VALUES(?,?,?,?,?,?,?)',(i,n,from_warehouse,to_warehouse,'draft',notes,now))
  for z in lines:
   sku=str(z.get('sku','')).strip();q=float(z.get('quantity',0))
   if not sku or q<=0:raise HTTPException(400,'Invalid transfer line')
   lid=str(uuid.uuid4());c.execute('INSERT INTO warehouse_transfer_lines(id,transfer_id,sku,requested_qty) VALUES(?,?,?,?)',(lid,i,sku,q));reserve_line(c,{'id':i,'from_warehouse':from_warehouse},{'id':lid,'sku':sku,'requested_qty':q},n)
  c.execute('COMMIT');return {'id':i,'transfer_no':n,'status':'draft','inventory_reserved':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/transfers/{transfer_id}/ship')
def ship(transfer_id:str,approval_id:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  t=c.execute('SELECT * FROM warehouse_transfer_orders WHERE id=?',(transfer_id,)).fetchone()
  if not t:raise HTTPException(404,'Transfer not found')
  if t['status']!='draft':raise HTTPException(400,'Only draft transfers can ship')
  consume_approval(c,approval_id,'transfer_ship',t['transfer_no'],t['from_warehouse'],'transfer_ship')
  lines=c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(transfer_id,)).fetchall();now=time.time()
  for l in lines:
   lots=c.execute("SELECT * FROM warehouse_transfer_lots WHERE transfer_line_id=? AND status='reserved'",(l['id'],)).fetchall()
   if abs(sum(float(z['quantity']) for z in lots)-float(l['requested_qty']))>0.000001:raise HTTPException(409,f'Transfer reservation incomplete for {l["sku"]}')
   if stock(c,l['sku'],t['from_warehouse'])<float(l['requested_qty']):raise HTTPException(409,f'Aggregate stock conflict for {l["sku"]}')
   change(c,l['sku'],t['from_warehouse'],-float(l['requested_qty']))
   for z in lots:
    physical=c.execute('SELECT quantity_available,status FROM warehouse_lots WHERE id=?',(z['source_lot_id'],)).fetchone()
    if not physical or physical['status']!='available' or float(physical['quantity_available'])<float(z['quantity']):raise HTTPException(409,f'Lot no longer available for {l["sku"]}')
    q=float(z['quantity']);c.execute("UPDATE warehouse_lots SET quantity_available=quantity_available-?,status=CASE WHEN quantity_available-?<=0 THEN 'depleted' ELSE status END,updated_at=? WHERE id=?",(q,q,now,z['source_lot_id']));c.execute("UPDATE warehouse_transfer_lots SET status='in_transit',shipped_at=? WHERE id=?",(now,z['id']))
    if z['source_location']:c.execute('UPDATE warehouse_locations SET used_capacity=MAX(0,used_capacity-?),updated_at=? WHERE warehouse_id=? AND location_code=?',(q,now,t['from_warehouse'],z['source_location']))
    emit(c,'transfer-ship:'+z['id'],z['sku'],'transfer_shipped',t['from_warehouse'],-q,z['lot_no'],z['batch_no'],'',z['source_location'],'IN_TRANSIT','transfer',t['transfer_no'],'system','Lot departed source warehouse',now)
   c.execute('UPDATE warehouse_transfer_lines SET shipped_qty=requested_qty WHERE id=?',(l['id'],))
  c.execute("UPDATE warehouse_transfer_orders SET status='in_transit',shipped_at=? WHERE id=?",(now,transfer_id));c.execute('COMMIT');return {'transfer_id':transfer_id,'status':'in_transit','approval_id':approval_id,'lot_controlled':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/transfers/{transfer_id}/receive')
def receive(transfer_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  t=c.execute('SELECT * FROM warehouse_transfer_orders WHERE id=?',(transfer_id,)).fetchone()
  if not t:raise HTTPException(404,'Transfer not found')
  if t['status']!='in_transit':raise HTTPException(400,'Transfer is not in transit')
  lines=c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(transfer_id,)).fetchall();now=time.time();assignments={}
  for z in c.execute("SELECT * FROM warehouse_transfer_lots WHERE transfer_id=? AND status='in_transit'",(transfer_id,)).fetchall():
   loc=destination(c,t['to_warehouse'],float(z['quantity']))
   if not loc:raise HTTPException(409,f'No destination bin capacity for {z["sku"]} lot {z["lot_no"] or "-"}')
   assignments[z['id']]=loc;c.execute('UPDATE warehouse_locations SET used_capacity=used_capacity+?,updated_at=? WHERE id=?',(float(z['quantity']),now,loc['id']))
  for l in lines:change(c,l['sku'],t['to_warehouse'],float(l['shipped_qty']));c.execute('UPDATE warehouse_transfer_lines SET received_qty=shipped_qty WHERE id=?',(l['id'],))
  for z in c.execute("SELECT * FROM warehouse_transfer_lots WHERE transfer_id=? AND status='in_transit'",(transfer_id,)).fetchall():
   loc=assignments[z['id']];lid=str(uuid.uuid4());q=float(z['quantity']);c.execute('INSERT INTO warehouse_lots(id,sku,warehouse_id,lot_no,batch_no,manufacture_date,expiry_date,received_at,quantity_received,quantity_available,location_code,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(lid,z['sku'],t['to_warehouse'],z['lot_no'],z['batch_no'],z['manufacture_date'],z['expiry_date'],now,q,q,loc['location_code'],'available',now,now));c.execute("UPDATE warehouse_transfer_lots SET status='received',destination_lot_id=?,destination_location=?,received_at=? WHERE id=?",(lid,loc['location_code'],now,z['id']));emit(c,'transfer-receive:'+z['id'],z['sku'],'transfer_received',t['to_warehouse'],q,z['lot_no'],z['batch_no'],'','IN_TRANSIT',loc['location_code'],'transfer',t['transfer_no'],'system','Lot received at destination warehouse',now)
  c.execute("UPDATE warehouse_transfer_orders SET status='received',received_at=? WHERE id=?",(now,transfer_id));c.execute('COMMIT');return {'transfer_id':transfer_id,'status':'received','lots_recreated':True,'capacity_updated':True}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/transfers')
def transfers(warehouse_id:str=Query(''),status:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_transfer_orders WHERE 1=1';a=[]
 if warehouse_id:q+=' AND (from_warehouse=? OR to_warehouse=?)';a += [warehouse_id,warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY created_at DESC';rows=[dict(r) for r in c.execute(q,a).fetchall()]
 for t in rows:t['lines']=[dict(x) for x in c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(t['id'],)).fetchall()];t['lots']=[dict(x) for x in c.execute('SELECT * FROM warehouse_transfer_lots WHERE transfer_id=? ORDER BY sku,lot_no',(t['id'],)).fetchall()]
 c.close();return {'results':rows}
@router.get('/warehouse/network-balance')
def balance(x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE enabled=1 ORDER BY sku,warehouse_id').fetchall();suggest=[];by={}
 for r in rules:by.setdefault(r['sku'],[]).append(r)
 for sku,rs in by.items():
  deficits=[];surplus=[]
  for r in rs:
   q=stock(c,sku,r['warehouse_id']);target=float(r['target_stock']);safety=float(r['safety_stock'])
   if q<safety:deficits.append([r['warehouse_id'],max(0,target-q)])
   elif q>target:surplus.append([r['warehouse_id'],q-target])
  for dw,need in deficits:
   for src in surplus:
    if need<=0:break
    take=min(need,src[1])
    if take>0:suggest.append({'sku':sku,'from_warehouse':src[0],'to_warehouse':dw,'quantity':round(take,2),'reason':'Network rebalance: destination below safety stock'});src[1]-=take;need-=take
 c.close();return {'count':len(suggest),'recommendations':suggest}

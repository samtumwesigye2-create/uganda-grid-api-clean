import os, sqlite3, time, uuid, json
from fastapi import APIRouter, Form, Header, HTTPException, Query
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');router=APIRouter();VALID={'receiving','putaway','storage','picking','packaging','dispatch','inventory_control','return','damaged','safety_security','documentation','layout','optimization','equipment_management','accuracy'}
def conn(): c=sqlite3.connect(DB_PATH,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init_db():
 c=conn();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_operations(id TEXT PRIMARY KEY,shipment_id TEXT,sku TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',operation_type TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,location_code TEXT,condition_code TEXT,note TEXT,status TEXT NOT NULL DEFAULT 'completed',created_at REAL NOT NULL)''');cols={r[1] for r in c.execute('PRAGMA table_info(warehouse_operations)').fetchall()}
 for n,t in [('reference_no','TEXT'),('action_code','TEXT'),('details_json','TEXT'),('updated_at','REAL'),('lot_no','TEXT'),('batch_no','TEXT'),('manufacture_date','TEXT'),('expiry_date','TEXT')]:
  if n not in cols:c.execute(f'ALTER TABLE warehouse_operations ADD COLUMN {n} {t}')
 c.execute('''CREATE TABLE IF NOT EXISTS warehouse_locations(id TEXT PRIMARY KEY,warehouse_id TEXT NOT NULL DEFAULT 'main',zone TEXT NOT NULL,aisle TEXT NOT NULL,rack TEXT NOT NULL,shelf TEXT NOT NULL,bin TEXT NOT NULL,location_code TEXT NOT NULL UNIQUE,capacity REAL NOT NULL DEFAULT 100,used_capacity REAL NOT NULL DEFAULT 0,location_type TEXT NOT NULL DEFAULT 'standard',status TEXT NOT NULL DEFAULT 'available',priority INTEGER NOT NULL DEFAULT 100,created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_lots(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',lot_no TEXT,batch_no TEXT,manufacture_date TEXT,expiry_date TEXT,received_at REAL NOT NULL,quantity_received REAL NOT NULL DEFAULT 0,quantity_available REAL NOT NULL DEFAULT 0,location_code TEXT,status TEXT NOT NULL DEFAULT 'available',created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_legacy_pick_reservations(id TEXT PRIMARY KEY,operation_id TEXT UNIQUE NOT NULL,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL,lot_id TEXT NOT NULL,location_code TEXT,quantity REAL NOT NULL,status TEXT NOT NULL DEFAULT 'picked',created_at REAL NOT NULL,dispatched_at REAL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_whlot_pick ON warehouse_lots(warehouse_id,sku,status,expiry_date,received_at)');c.commit();c.close()
init_db()
def stock_delta(c,sku,w,d,m,n):
 if not sku or not d:return
 if not c.execute('SELECT sku FROM products WHERE sku=?',(sku,)).fetchone():raise HTTPException(404,'Product SKU not found')
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();old=float(r['quantity_on_hand']) if r else 0;new=old+d
 if new<0:raise HTTPException(400,'Insufficient stock for this operation')
 if r:c.execute('UPDATE stock SET quantity_on_hand=? WHERE product_sku=? AND warehouse_id=?',(new,sku,w))
 else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,w,new))
 c.execute('INSERT INTO stock_movements(id,product_sku,warehouse_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),sku,w,m,abs(d),n,time.time()))
def ref_for(op):return f"{{'receiving':'GRN','dispatch':'GATE','picking':'PICK','packaging':'PACK','putaway':'PUT','inventory_control':'COUNT','return':'RTN','damaged':'DMG'}.get(op,'WH')}-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
def allocate_lots(c,sku,w,qty,strategy='fifo'):
 order="CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END,expiry_date ASC,received_at ASC" if strategy.lower()=='fefo' else 'received_at ASC';rows=c.execute(f"SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available' AND quantity_available>0 ORDER BY {order}",(sku,w)).fetchall();need=qty;out=[]
 for r in rows:
  if need<=0:break
  held=c.execute("SELECT COALESCE(SUM(quantity),0) q FROM warehouse_legacy_pick_reservations WHERE lot_id=? AND status='picked'",(r['id'],)).fetchone();free=max(0,float(r['quantity_available'])-float(held['q'] or 0));take=min(free,need)
  if take>0:out.append({'lot_id':r['id'],'lot_no':r['lot_no'],'batch_no':r['batch_no'],'expiry_date':r['expiry_date'],'location_code':r['location_code'],'quantity':take});need-=take
 if need>0:raise HTTPException(400,'Insufficient unreserved FIFO/FEFO lot stock')
 return out
@router.get('/warehouse/lots')
def lots(sku:str=Query(''),warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();q='SELECT * FROM warehouse_lots WHERE warehouse_id=?';a=[warehouse_id]
 if sku:q+=' AND sku=?';a.append(sku)
 q+=' ORDER BY sku,expiry_date,received_at';r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.get('/warehouse/picking/allocate')
def picking_allocate(sku:str=Query(...),warehouse_id:str=Query('main'),quantity:float=Query(...,gt=0),strategy:str=Query('fefo'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();out=allocate_lots(c,sku,warehouse_id,quantity,strategy);c.close();return {'sku':sku,'strategy':strategy.upper(),'requested':quantity,'allocated':sum(x['quantity'] for x in out),'short':0,'allocations':[{**x,'pick_quantity':x['quantity']} for x in out]}
@router.post('/warehouse/operations')
def create_operation(operation_type:str=Form(...),shipment_id:str=Form(''),sku:str=Form(''),warehouse_id:str=Form('main'),quantity:float=Form(0),location_code:str=Form(''),condition_code:str=Form('good'),note:str=Form(''),action_code:str=Form(''),details_json:str=Form('{}'),status:str=Form('completed'),lot_no:str=Form(''),batch_no:str=Form(''),manufacture_date:str=Form(''),expiry_date:str=Form(''),allocation_strategy:str=Form('fefo'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');op=operation_type.strip().lower()
 if op not in VALID:raise HTTPException(400,'Invalid warehouse operation')
 try:details=json.loads(details_json or '{}')
 except:raise HTTPException(400,'Invalid operation details')
 c=conn();c.execute('BEGIN IMMEDIATE')
 try:
  allocations=[];oid=str(uuid.uuid4());now=time.time();reference=ref_for(op)
  if op=='receiving' and action_code=='receive':stock_delta(c,sku,warehouse_id,quantity,'receive',note or 'Warehouse receiving');c.execute('INSERT INTO warehouse_lots(id,sku,warehouse_id,lot_no,batch_no,manufacture_date,expiry_date,received_at,quantity_received,quantity_available,location_code,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),sku,warehouse_id,lot_no,batch_no,manufacture_date,expiry_date,now,quantity,quantity,location_code.upper(),'available',now,now))
  elif op=='picking' and action_code=='pick':
   allocations=allocate_lots(c,sku,warehouse_id,quantity,allocation_strategy)
   for a in allocations:c.execute('INSERT INTO warehouse_legacy_pick_reservations VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),oid,sku,warehouse_id,a['lot_id'],a['location_code'],a['quantity'],'picked',now,None))
  elif op=='dispatch' and action_code=='dispatch':
   picks=c.execute("SELECT * FROM warehouse_legacy_pick_reservations WHERE sku=? AND warehouse_id=? AND status='picked' ORDER BY created_at",(sku,warehouse_id)).fetchall();need=quantity;used=[]
   for p in picks:
    if need<=0:break
    take=min(float(p['quantity']),need)
    if take<float(p['quantity']):raise HTTPException(400,'Dispatch quantity must match picked reservation quantities')
    used.append(p);need-=take
   if need>0:raise HTTPException(400,'Dispatch requires previously picked inventory')
   stock_delta(c,sku,warehouse_id,-quantity,'dispatch',note or 'Warehouse dispatch')
   for p in used:
    q=float(p['quantity']);lot=c.execute('SELECT quantity_available FROM warehouse_lots WHERE id=?',(p['lot_id'],)).fetchone()
    if not lot or float(lot['quantity_available'])<q:raise HTTPException(409,'Lot inventory conflict')
    c.execute("UPDATE warehouse_lots SET quantity_available=quantity_available-?,status=CASE WHEN quantity_available-?<=0 THEN 'depleted' ELSE status END,updated_at=? WHERE id=?",(q,q,time.time(),p['lot_id']));c.execute("UPDATE warehouse_legacy_pick_reservations SET status='dispatched',dispatched_at=? WHERE id=?",(time.time(),p['id']))
    if p['location_code']:c.execute('UPDATE warehouse_locations SET used_capacity=MAX(0,used_capacity-?),updated_at=? WHERE warehouse_id=? AND location_code=?',(q,time.time(),warehouse_id,p['location_code']))
  elif op=='return' and action_code=='restock':stock_delta(c,sku,warehouse_id,quantity,'return',note or 'Returned stock')
  elif op=='damaged' and action_code=='write_off':stock_delta(c,sku,warehouse_id,-quantity,'damaged',note or 'Damaged stock removed')
  if op=='putaway' and location_code and action_code=='confirm_bin':
   loc=c.execute('SELECT * FROM warehouse_locations WHERE location_code=? AND warehouse_id=?',(location_code.upper(),warehouse_id)).fetchone()
   if not loc:raise HTTPException(404,'Warehouse location not found')
   if float(loc['used_capacity'])+quantity>float(loc['capacity']):raise HTTPException(400,'Location capacity exceeded')
   q="SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available'";a=[sku,warehouse_id]
   if lot_no:q+=' AND lot_no=?';a.append(lot_no)
   elif batch_no:q+=' AND batch_no=?';a.append(batch_no)
   else:raise HTTPException(400,'Put-away requires lot number or batch number')
   target=c.execute(q,a).fetchone()
   if not target:raise HTTPException(404,'Target lot/batch not found')
   if quantity>float(target['quantity_available']):raise HTTPException(400,'Put-away quantity exceeds lot quantity')
   c.execute('UPDATE warehouse_locations SET used_capacity=used_capacity+?,updated_at=? WHERE id=?',(quantity,time.time(),loc['id']));c.execute('UPDATE warehouse_lots SET location_code=?,updated_at=? WHERE id=?',(location_code.upper(),time.time(),target['id']))
  details['allocations']=allocations;c.execute('INSERT INTO warehouse_operations(id,shipment_id,sku,warehouse_id,operation_type,quantity,location_code,condition_code,note,status,created_at,reference_no,action_code,details_json,updated_at,lot_no,batch_no,manufacture_date,expiry_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,shipment_id,sku,warehouse_id,op,quantity,location_code.upper(),condition_code,note,status,now,reference,action_code,json.dumps(details),now,lot_no,batch_no,manufacture_date,expiry_date));c.commit();return dict(c.execute('SELECT * FROM warehouse_operations WHERE id=?',(oid,)).fetchone())
 except Exception:c.rollback();raise
 finally:c.close()
@router.get('/warehouse/operations')
def list_operations(operation_type:str=Query(''),shipment_id:str=Query(''),limit:int=Query(100,ge=1,le=500),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');q='SELECT * FROM warehouse_operations WHERE 1=1';a=[]
 if operation_type:q+=' AND operation_type=?';a.append(operation_type)
 if shipment_id:q+=' AND shipment_id=?';a.append(shipment_id)
 q+=' ORDER BY created_at DESC LIMIT ?';a.append(limit);c=conn();r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}

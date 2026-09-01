import os, sqlite3, time, uuid, json
from fastapi import APIRouter, Form, Header, HTTPException, Query
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');router=APIRouter();VALID={'receiving','putaway','storage','picking','packaging','dispatch','inventory_control','return','damaged','safety_security','documentation','layout','optimization','equipment_management','accuracy'}
def conn(): c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def init_db():
 c=conn();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_operations(id TEXT PRIMARY KEY,shipment_id TEXT,sku TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',operation_type TEXT NOT NULL,quantity REAL NOT NULL DEFAULT 0,location_code TEXT,condition_code TEXT,note TEXT,status TEXT NOT NULL DEFAULT 'completed',created_at REAL NOT NULL)''');cols={r[1] for r in c.execute('PRAGMA table_info(warehouse_operations)').fetchall()}
 for n,t in [('reference_no','TEXT'),('action_code','TEXT'),('details_json','TEXT'),('updated_at','REAL'),('lot_no','TEXT'),('batch_no','TEXT'),('manufacture_date','TEXT'),('expiry_date','TEXT')]:
  if n not in cols:c.execute(f'ALTER TABLE warehouse_operations ADD COLUMN {n} {t}')
 c.execute('''CREATE TABLE IF NOT EXISTS warehouse_locations(id TEXT PRIMARY KEY,warehouse_id TEXT NOT NULL DEFAULT 'main',zone TEXT NOT NULL,aisle TEXT NOT NULL,rack TEXT NOT NULL,shelf TEXT NOT NULL,bin TEXT NOT NULL,location_code TEXT NOT NULL UNIQUE,capacity REAL NOT NULL DEFAULT 100,used_capacity REAL NOT NULL DEFAULT 0,location_type TEXT NOT NULL DEFAULT 'standard',status TEXT NOT NULL DEFAULT 'available',priority INTEGER NOT NULL DEFAULT 100,created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
 c.execute('''CREATE TABLE IF NOT EXISTS warehouse_lots(id TEXT PRIMARY KEY,sku TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',lot_no TEXT,batch_no TEXT,manufacture_date TEXT,expiry_date TEXT,received_at REAL NOT NULL,quantity_received REAL NOT NULL DEFAULT 0,quantity_available REAL NOT NULL DEFAULT 0,location_code TEXT,status TEXT NOT NULL DEFAULT 'available',created_at REAL NOT NULL,updated_at REAL NOT NULL)''');c.execute('CREATE INDEX IF NOT EXISTS idx_whlot_pick ON warehouse_lots(warehouse_id,sku,status,expiry_date,received_at)');c.execute('CREATE INDEX IF NOT EXISTS idx_whloc_wh ON warehouse_locations(warehouse_id,status)');c.commit();c.close()
init_db()
def stock_delta(c,sku,w,d,m,n):
 if not sku or not d:return
 if not c.execute('SELECT sku FROM products WHERE sku=?',(sku,)).fetchone():raise HTTPException(404,'Product SKU not found')
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();old=float(r['quantity_on_hand']) if r else 0;new=old+d
 if new<0:raise HTTPException(400,'Insufficient stock for this operation')
 if r:c.execute('UPDATE stock SET quantity_on_hand=? WHERE product_sku=? AND warehouse_id=?',(new,sku,w))
 else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,w,new))
 c.execute('INSERT INTO stock_movements(id,product_sku,warehouse_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),sku,w,m,abs(d),n,time.time()))
def ref_for(op):
 p={'receiving':'GRN','dispatch':'GATE','picking':'PICK','packaging':'PACK','putaway':'PUT','inventory_control':'COUNT','return':'RTN','damaged':'DMG','safety_security':'SAFE','equipment_management':'EQP','documentation':'DOC'}.get(op,'WH');return f'{p}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def consume_lots(c,sku,w,qty,strategy='fifo'):
 order="CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END,expiry_date ASC,received_at ASC" if strategy.lower()=='fefo' else 'received_at ASC'
 rows=c.execute(f"SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available' AND quantity_available>0 ORDER BY {order}",(sku,w)).fetchall();need=qty;alloc=[]
 for r in rows:
  if need<=0:break
  take=min(float(r['quantity_available']),need);new=float(r['quantity_available'])-take;c.execute("UPDATE warehouse_lots SET quantity_available=?,status=?,updated_at=? WHERE id=?",(new,'depleted' if new<=0 else 'available',time.time(),r['id']));alloc.append({'lot_id':r['id'],'lot_no':r['lot_no'],'batch_no':r['batch_no'],'expiry_date':r['expiry_date'],'location_code':r['location_code'],'quantity':take});need-=take
 if need>0:raise HTTPException(400,'Insufficient FIFO/FEFO lot stock')
 return alloc
@router.get('/warehouse/lots')
def lots(sku:str=Query(''),warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();q='SELECT * FROM warehouse_lots WHERE warehouse_id=?';a=[warehouse_id]
 if sku:q+=' AND sku=?';a.append(sku)
 q+=' ORDER BY sku,expiry_date,received_at';r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.get('/warehouse/picking/allocate')
def picking_allocate(sku:str=Query(...),warehouse_id:str=Query('main'),quantity:float=Query(...,gt=0),strategy:str=Query('fefo'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();order="CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END,expiry_date ASC,received_at ASC" if strategy.lower()=='fefo' else 'received_at ASC';rows=c.execute(f"SELECT * FROM warehouse_lots WHERE sku=? AND warehouse_id=? AND status='available' AND quantity_available>0 ORDER BY {order}",(sku,warehouse_id)).fetchall();c.close();need=quantity;out=[]
 for r in rows:
  if need<=0:break
  take=min(float(r['quantity_available']),need);out.append({**dict(r),'pick_quantity':take});need-=take
 return {'sku':sku,'strategy':strategy.upper(),'requested':quantity,'allocated':quantity-need,'short':max(0,need),'allocations':out}
@router.post('/warehouse/locations')
def create_location(warehouse_id:str=Form('main'),zone:str=Form(...),aisle:str=Form(...),rack:str=Form(...),shelf:str=Form(...),bin:str=Form(...),capacity:float=Form(100),location_type:str=Form('standard'),priority:int=Form(100),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');parts=[zone,aisle,rack,shelf,bin];code='-'.join(str(x).strip().upper().replace(' ','') for x in parts);c=conn()
 try:
  now=time.time();oid=str(uuid.uuid4());c.execute("INSERT INTO warehouse_locations(id,warehouse_id,zone,aisle,rack,shelf,bin,location_code,capacity,used_capacity,location_type,status,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,0,?,'available',?,?,?)",(oid,warehouse_id,*[str(x).strip().upper() for x in parts],code,capacity,location_type,priority,now,now));c.commit();return dict(c.execute('SELECT * FROM warehouse_locations WHERE id=?',(oid,)).fetchone())
 except sqlite3.IntegrityError:raise HTTPException(409,'Location code already exists')
 finally:c.close()
@router.get('/warehouse/locations')
def locations(warehouse_id:str=Query('main'),status:str=Query(''),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();q='SELECT *,ROUND(CASE WHEN capacity>0 THEN used_capacity*100.0/capacity ELSE 0 END,1) utilization FROM warehouse_locations WHERE warehouse_id=?';a=[warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY zone,aisle,rack,shelf,bin';r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.get('/warehouse/putaway/suggest')
def suggest_putaway(sku:str=Query(''),warehouse_id:str=Query('main'),quantity:float=Query(1,ge=0),strategy:str=Query('fifo'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();r=c.execute("SELECT *,capacity-used_capacity free_capacity FROM warehouse_locations WHERE warehouse_id=? AND status='available' AND capacity-used_capacity>=? ORDER BY CASE WHEN location_type='fast_pick' THEN 0 ELSE 1 END,priority,used_capacity LIMIT 10",(warehouse_id,quantity)).fetchall();c.close();return {'sku':sku,'quantity':quantity,'strategy':strategy.upper(),'suggestions':[dict(x) for x in r]}
@router.post('/warehouse/operations')
def create_operation(operation_type:str=Form(...),shipment_id:str=Form(''),sku:str=Form(''),warehouse_id:str=Form('main'),quantity:float=Form(0),location_code:str=Form(''),condition_code:str=Form('good'),note:str=Form(''),action_code:str=Form(''),details_json:str=Form('{}'),status:str=Form('completed'),lot_no:str=Form(''),batch_no:str=Form(''),manufacture_date:str=Form(''),expiry_date:str=Form(''),allocation_strategy:str=Form('fefo'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');op=operation_type.strip().lower()
 if op not in VALID:raise HTTPException(400,'Invalid warehouse operation')
 try:details=json.loads(details_json or '{}')
 except:raise HTTPException(400,'Invalid operation details')
 c=conn()
 try:
  allocations=[]
  if op=='receiving' and action_code=='receive':
   stock_delta(c,sku,warehouse_id,quantity,'receive',note or 'Warehouse receiving');now=time.time();c.execute('INSERT INTO warehouse_lots(id,sku,warehouse_id,lot_no,batch_no,manufacture_date,expiry_date,received_at,quantity_received,quantity_available,location_code,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),sku,warehouse_id,lot_no,batch_no,manufacture_date,expiry_date,now,quantity,quantity,location_code.upper(),'available',now,now))
  elif op=='picking' and action_code=='pick':stock_delta(c,sku,warehouse_id,-quantity,'pick',note or 'Warehouse picking');allocations=consume_lots(c,sku,warehouse_id,quantity,allocation_strategy)
  elif op=='dispatch' and action_code=='dispatch':stock_delta(c,sku,warehouse_id,-quantity,'dispatch',note or 'Warehouse dispatch')
  elif op=='return' and action_code=='restock':stock_delta(c,sku,warehouse_id,quantity,'return',note or 'Returned stock')
  elif op=='damaged' and action_code=='write_off':stock_delta(c,sku,warehouse_id,-quantity,'damaged',note or 'Damaged stock removed')
  if op=='putaway' and location_code and action_code=='confirm_bin':
   loc=c.execute('SELECT * FROM warehouse_locations WHERE location_code=? AND warehouse_id=?',(location_code.upper(),warehouse_id)).fetchone()
   if not loc:raise HTTPException(404,'Warehouse location not found')
   if float(loc['used_capacity'])+quantity>float(loc['capacity']):raise HTTPException(400,'Location capacity exceeded')
   c.execute('UPDATE warehouse_locations SET used_capacity=used_capacity+?,updated_at=? WHERE id=?',(quantity,time.time(),loc['id']));c.execute("UPDATE warehouse_lots SET location_code=?,updated_at=? WHERE sku=? AND warehouse_id=? AND (location_code='' OR location_code IS NULL) AND status='available'",(location_code.upper(),time.time(),sku,warehouse_id))
  details['allocations']=allocations;oid=str(uuid.uuid4());now=time.time();reference=ref_for(op);c.execute('INSERT INTO warehouse_operations(id,shipment_id,sku,warehouse_id,operation_type,quantity,location_code,condition_code,note,status,created_at,reference_no,action_code,details_json,updated_at,lot_no,batch_no,manufacture_date,expiry_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,shipment_id,sku,warehouse_id,op,quantity,location_code.upper(),condition_code,note,status,now,reference,action_code,json.dumps(details),now,lot_no,batch_no,manufacture_date,expiry_date));c.commit();return dict(c.execute('SELECT * FROM warehouse_operations WHERE id=?',(oid,)).fetchone())
 finally:c.close()
@router.get('/warehouse/operations')
def list_operations(operation_type:str=Query(''),shipment_id:str=Query(''),limit:int=Query(100,ge=1,le=500),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');q='SELECT * FROM warehouse_operations WHERE 1=1';a=[]
 if operation_type:q+=' AND operation_type=?';a.append(operation_type)
 if shipment_id:q+=' AND shipment_id=?';a.append(shipment_id)
 q+=' ORDER BY created_at DESC LIMIT ?';a.append(limit);c=conn();r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.get('/warehouse/dashboard')
def warehouse_dashboard(x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();now=time.time();ops=c.execute('SELECT operation_type,COUNT(*) n FROM warehouse_operations WHERE created_at>=? GROUP BY operation_type',(now-86400,)).fetchall();alerts=[]
 for r in c.execute("SELECT reference_no,sku,quantity FROM warehouse_operations WHERE operation_type='damaged' AND created_at>=? LIMIT 10",(now-604800,)).fetchall():alerts.append({'level':'warning','type':'damage','message':f"Damage: {r['sku']} qty {r['quantity']}",'reference':r['reference_no']})
 exp=c.execute("SELECT sku,lot_no,batch_no,expiry_date,quantity_available,location_code FROM warehouse_lots WHERE status='available' AND expiry_date!='' AND expiry_date IS NOT NULL AND date(expiry_date)<=date('now','+30 day') ORDER BY expiry_date LIMIT 20").fetchall()
 for r in exp:alerts.append({'level':'warning','type':'expiry','message':f"Expiry {r['expiry_date']}: {r['sku']} lot {r['lot_no'] or r['batch_no'] or '-'} qty {r['quantity_available']}",'reference':r['location_code']})
 stock=c.execute('SELECT product_sku,warehouse_id,quantity_on_hand FROM stock ORDER BY quantity_on_hand ASC LIMIT 20').fetchall();low=[dict(r) for r in stock if float(r['quantity_on_hand'] or 0)<=5];loc=c.execute('SELECT COUNT(*) total,SUM(CASE WHEN used_capacity>=capacity THEN 1 ELSE 0 END) full,ROUND(AVG(CASE WHEN capacity>0 THEN used_capacity*100.0/capacity ELSE 0 END),1) utilization FROM warehouse_locations').fetchone();c.close();return {'today':{r['operation_type']:r['n'] for r in ops},'alerts':alerts,'low_stock':low,'locations':dict(loc),'generated_at':now}

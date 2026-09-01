import os, sqlite3, time, uuid, json
from fastapi import APIRouter, Form, Header, HTTPException, Query
from auth import require_permission

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'data_hub.db')
router=APIRouter()
VALID={'receiving','putaway','storage','picking','packaging','dispatch','inventory_control','return','damaged','safety_security','documentation','layout','optimization','equipment_management','accuracy'}

def conn():
    c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c

def init_db():
    c=conn();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_operations (
      id TEXT PRIMARY KEY, shipment_id TEXT, sku TEXT,
      warehouse_id TEXT NOT NULL DEFAULT 'main', operation_type TEXT NOT NULL,
      quantity REAL NOT NULL DEFAULT 0, location_code TEXT, condition_code TEXT,
      note TEXT, status TEXT NOT NULL DEFAULT 'completed', created_at REAL NOT NULL
    )''')
    cols={r[1] for r in c.execute('PRAGMA table_info(warehouse_operations)').fetchall()}
    for name,typ in [('reference_no','TEXT'),('action_code','TEXT'),('details_json','TEXT'),('updated_at','REAL')]:
        if name not in cols:c.execute(f'ALTER TABLE warehouse_operations ADD COLUMN {name} {typ}')
    c.commit();c.close()
init_db()

def stock_delta(c,sku,warehouse_id,delta,movement_type,note):
    if not sku or not delta:return
    p=c.execute('SELECT sku FROM products WHERE sku=?',(sku,)).fetchone()
    if not p:raise HTTPException(status_code=404,detail='Product SKU not found')
    r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,warehouse_id)).fetchone()
    old=float(r['quantity_on_hand']) if r else 0;new=old+delta
    if new<0:raise HTTPException(status_code=400,detail='Insufficient stock for this operation')
    if r:c.execute('UPDATE stock SET quantity_on_hand=? WHERE product_sku=? AND warehouse_id=?',(new,sku,warehouse_id))
    else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,warehouse_id,new))
    c.execute('INSERT INTO stock_movements(id,product_sku,warehouse_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),sku,warehouse_id,movement_type,abs(delta),note,time.time()))

def ref_for(op):
    prefix={'receiving':'GRN','dispatch':'GATE','picking':'PICK','packaging':'PACK','putaway':'PUT','inventory_control':'COUNT','return':'RTN','damaged':'DMG','safety_security':'SAFE','equipment_management':'EQP','documentation':'DOC'}.get(op,'WH')
    return f'{prefix}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'

@router.post('/warehouse/operations')
def create_operation(operation_type:str=Form(...),shipment_id:str=Form(''),sku:str=Form(''),warehouse_id:str=Form('main'),quantity:float=Form(0),location_code:str=Form(''),condition_code:str=Form('good'),note:str=Form(''),action_code:str=Form(''),details_json:str=Form('{}'),status:str=Form('completed'),x_access_code:str=Header(default='')):
    require_permission(x_access_code,'inventory:write');op=operation_type.strip().lower()
    if op not in VALID:raise HTTPException(status_code=400,detail='Invalid warehouse operation')
    if quantity<0:raise HTTPException(status_code=400,detail='Quantity cannot be negative')
    try:json.loads(details_json or '{}')
    except Exception:raise HTTPException(status_code=400,detail='Invalid operation details')
    c=conn()
    try:
        if op=='receiving' and action_code in {'receive','create_grn'}:stock_delta(c,sku,warehouse_id,quantity,'receive',note or 'Warehouse receiving')
        elif op=='picking' and action_code in {'pick','scan_verify'}:stock_delta(c,sku,warehouse_id,-quantity,'pick',note or 'Warehouse picking')
        elif op=='dispatch' and action_code in {'dispatch','gate_pass'}:stock_delta(c,sku,warehouse_id,-quantity,'dispatch',note or 'Warehouse dispatch')
        elif op=='return' and action_code in {'return_good','restock'}:stock_delta(c,sku,warehouse_id,quantity,'return',note or 'Returned stock')
        elif op=='damaged' and action_code in {'write_off','quarantine'}:stock_delta(c,sku,warehouse_id,-quantity,'damaged',note or 'Damaged stock removed')
        oid=str(uuid.uuid4());now=time.time();reference=ref_for(op)
        c.execute('''INSERT INTO warehouse_operations(id,shipment_id,sku,warehouse_id,operation_type,quantity,location_code,condition_code,note,status,created_at,reference_no,action_code,details_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(oid,shipment_id,sku,warehouse_id,op,quantity,location_code,condition_code,note,status,now,reference,action_code,details_json,now));c.commit();row=c.execute('SELECT * FROM warehouse_operations WHERE id=?',(oid,)).fetchone();return dict(row)
    finally:c.close()

@router.get('/warehouse/operations')
def list_operations(operation_type:str=Query(''),shipment_id:str=Query(''),limit:int=Query(100,ge=1,le=500),x_access_code:str=Header(default='')):
    require_permission(x_access_code,'inventory:read');q='SELECT * FROM warehouse_operations WHERE 1=1';args=[]
    if operation_type:q+=' AND operation_type=?';args.append(operation_type.strip().lower())
    if shipment_id:q+=' AND shipment_id=?';args.append(shipment_id.strip())
    q+=' ORDER BY created_at DESC LIMIT ?';args.append(limit);c=conn();rows=c.execute(q,args).fetchall();c.close();return {'count':len(rows),'results':[dict(r) for r in rows]}

@router.get('/warehouse/operations/summary')
def operation_summary(x_access_code:str=Header(default='')):
    require_permission(x_access_code,'inventory:read');c=conn();rows=c.execute('SELECT operation_type,COUNT(*) count,SUM(quantity) quantity FROM warehouse_operations GROUP BY operation_type').fetchall();c.close();base={k:{'count':0,'quantity':0} for k in sorted(VALID)}
    for r in rows:base[r['operation_type']]={'count':r['count'],'quantity':r['quantity'] or 0}
    return {'operations':base}

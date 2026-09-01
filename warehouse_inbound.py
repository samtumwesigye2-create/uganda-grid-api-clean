import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
BASE_DIR=os.path.dirname(os.path.abspath(__file__));DB_PATH=os.path.join(BASE_DIR,'data_hub.db');router=APIRouter()
def conn():c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
def init_db():
 c=conn();c.executescript('''CREATE TABLE IF NOT EXISTS warehouse_suppliers(id TEXT PRIMARY KEY,supplier_code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,contact_name TEXT,email TEXT,phone TEXT,address TEXT,status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL,updated_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS warehouse_purchase_orders(id TEXT PRIMARY KEY,po_number TEXT NOT NULL UNIQUE,supplier_id TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',expected_date TEXT,status TEXT NOT NULL DEFAULT 'open',notes TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);CREATE TABLE IF NOT EXISTS warehouse_po_lines(id TEXT PRIMARY KEY,po_id TEXT NOT NULL,sku TEXT NOT NULL,description TEXT,ordered_qty REAL NOT NULL DEFAULT 0,received_qty REAL NOT NULL DEFAULT 0,uom TEXT NOT NULL DEFAULT 'each');CREATE TABLE IF NOT EXISTS warehouse_asn(id TEXT PRIMARY KEY,asn_number TEXT NOT NULL UNIQUE,po_id TEXT NOT NULL,carrier TEXT,tracking_no TEXT,eta TEXT,status TEXT NOT NULL DEFAULT 'expected',notes TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);''');c.commit();c.close()
init_db()
def num(prefix):return f'{prefix}-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
@router.post('/warehouse/suppliers')
def supplier(name:str=Form(...),supplier_code:str=Form(''),contact_name:str=Form(''),email:str=Form(''),phone:str=Form(''),address:str=Form(''),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');c=conn();now=time.time();sid=str(uuid.uuid4());code=(supplier_code.strip().upper() or 'SUP-'+uuid.uuid4().hex[:6].upper())
 try:c.execute('INSERT INTO warehouse_suppliers VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,code,name,contact_name,email,phone,address,'active',now,now));c.commit();return dict(c.execute('SELECT * FROM warehouse_suppliers WHERE id=?',(sid,)).fetchone())
 except sqlite3.IntegrityError:raise HTTPException(409,'Supplier code already exists')
 finally:c.close()
@router.get('/warehouse/suppliers')
def suppliers(x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();r=c.execute("SELECT * FROM warehouse_suppliers WHERE status='active' ORDER BY name").fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.post('/warehouse/purchase-orders')
def create_po(supplier_id:str=Form(...),warehouse_id:str=Form('main'),expected_date:str=Form(''),notes:str=Form(''),lines_json:str=Form('[]'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write')
 try:lines=json.loads(lines_json)
 except:raise HTTPException(400,'Invalid PO lines')
 if not isinstance(lines,list) or not lines:raise HTTPException(400,'Purchase order requires at least one line')
 c=conn();sup=c.execute('SELECT id FROM warehouse_suppliers WHERE id=?',(supplier_id,)).fetchone()
 if not sup:c.close();raise HTTPException(404,'Supplier not found')
 pid=str(uuid.uuid4());po=num('PO');now=time.time();c.execute('INSERT INTO warehouse_purchase_orders VALUES(?,?,?,?,?,?,?,?,?)',(pid,po,supplier_id,warehouse_id,expected_date,'open',notes,now,now))
 for x in lines:
  sku=str(x.get('sku','')).strip();qty=float(x.get('quantity',0) or 0)
  if not sku or qty<=0:continue
  c.execute('INSERT INTO warehouse_po_lines VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),pid,sku,str(x.get('description','')),qty,0,str(x.get('uom','each'))))
 if not c.execute('SELECT 1 FROM warehouse_po_lines WHERE po_id=?',(pid,)).fetchone():c.rollback();c.close();raise HTTPException(400,'No valid PO lines')
 c.commit();r=dict(c.execute('SELECT * FROM warehouse_purchase_orders WHERE id=?',(pid,)).fetchone());r['po_number']=po;c.close();return r
@router.get('/warehouse/purchase-orders')
def purchase_orders(status:str=Query('open'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();q='''SELECT p.*,s.name supplier_name,s.supplier_code FROM warehouse_purchase_orders p JOIN warehouse_suppliers s ON s.id=p.supplier_id''';a=[]
 if status:q+=' WHERE p.status=?';a.append(status)
 q+=' ORDER BY p.created_at DESC';rows=c.execute(q,a).fetchall();out=[]
 for r in rows:
  d=dict(r);d['lines']=[dict(x) for x in c.execute('SELECT * FROM warehouse_po_lines WHERE po_id=?',(r['id'],)).fetchall()];out.append(d)
 c.close();return {'count':len(out),'results':out}
@router.post('/warehouse/asn')
def create_asn(po_id:str=Form(...),carrier:str=Form(''),tracking_no:str=Form(''),eta:str=Form(''),notes:str=Form(''),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');c=conn()
 if not c.execute('SELECT id FROM warehouse_purchase_orders WHERE id=?',(po_id,)).fetchone():c.close();raise HTTPException(404,'Purchase order not found')
 aid=str(uuid.uuid4());asn=num('ASN');now=time.time();c.execute('INSERT INTO warehouse_asn VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,asn,po_id,carrier,tracking_no,eta,'expected',notes,now,now));c.commit();r=dict(c.execute('SELECT * FROM warehouse_asn WHERE id=?',(aid,)).fetchone());c.close();return r
@router.get('/warehouse/asn')
def asn(status:str=Query('expected'),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:read');c=conn();q='''SELECT a.*,p.po_number,p.warehouse_id,s.name supplier_name FROM warehouse_asn a JOIN warehouse_purchase_orders p ON p.id=a.po_id JOIN warehouse_suppliers s ON s.id=p.supplier_id''';a=[]
 if status:q+=' WHERE a.status=?';a.append(status)
 q+=' ORDER BY a.eta,a.created_at';r=c.execute(q,a).fetchall();c.close();return {'count':len(r),'results':[dict(x) for x in r]}
@router.post('/warehouse/purchase-orders/{po_id}/receive')
def receive_po(po_id:str,sku:str=Form(...),quantity:float=Form(...),x_access_code:str=Header(default='')):
 require_permission(x_access_code,'inventory:write');c=conn();line=c.execute('SELECT * FROM warehouse_po_lines WHERE po_id=? AND sku=?',(po_id,sku)).fetchone()
 if not line:c.close();raise HTTPException(404,'SKU is not on this purchase order')
 if quantity<=0:c.close();raise HTTPException(400,'Received quantity must be greater than zero')
 new=float(line['received_qty'])+quantity;c.execute('UPDATE warehouse_po_lines SET received_qty=? WHERE id=?',(new,line['id']));remaining=c.execute('SELECT COUNT(*) n FROM warehouse_po_lines WHERE po_id=? AND received_qty<ordered_qty',(po_id,)).fetchone()['n'];status='received' if remaining==0 else 'partial';c.execute('UPDATE warehouse_purchase_orders SET status=?,updated_at=? WHERE id=?',(status,time.time(),po_id));c.commit();c.close();return {'po_id':po_id,'sku':sku,'received_now':quantity,'received_total':new,'po_status':status}

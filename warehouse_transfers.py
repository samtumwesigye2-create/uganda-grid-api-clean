import os,sqlite3,time,uuid,json
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfer_orders(id TEXT PRIMARY KEY,transfer_no TEXT UNIQUE NOT NULL,from_warehouse TEXT NOT NULL,to_warehouse TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',notes TEXT,created_at REAL NOT NULL,shipped_at REAL,received_at REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfer_lines(id TEXT PRIMARY KEY,transfer_id TEXT NOT NULL,sku TEXT NOT NULL,requested_qty REAL NOT NULL,shipped_qty REAL NOT NULL DEFAULT 0,received_qty REAL NOT NULL DEFAULT 0)''');c.execute('CREATE INDEX IF NOT EXISTS idx_transfer_status ON warehouse_transfer_orders(status,from_warehouse,to_warehouse)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def no():return f'TRF-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def stock(c,sku,w):
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone();return float(r['quantity_on_hand']) if r else 0
def change(c,sku,w,q):
 r=c.execute('SELECT quantity_on_hand FROM stock WHERE product_sku=? AND warehouse_id=?',(sku,w)).fetchone()
 if r:c.execute('UPDATE stock SET quantity_on_hand=quantity_on_hand+? WHERE product_sku=? AND warehouse_id=?',(q,sku,w))
 else:c.execute('INSERT INTO stock(product_sku,warehouse_id,quantity_on_hand) VALUES(?,?,?)',(sku,w,q))
@router.post('/warehouse/transfers')
def create(from_warehouse:str=Form(...),to_warehouse:str=Form(...),lines_json:str=Form('[]'),notes:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if from_warehouse==to_warehouse:raise HTTPException(400,'Source and destination warehouses must differ')
 try:lines=json.loads(lines_json)
 except:raise HTTPException(400,'Invalid transfer lines')
 if not lines:raise HTTPException(400,'Transfer requires at least one line')
 c=db();i=str(uuid.uuid4());n=no();c.execute('INSERT INTO warehouse_transfer_orders(id,transfer_no,from_warehouse,to_warehouse,status,notes,created_at) VALUES(?,?,?,?,?,?,?)',(i,n,from_warehouse,to_warehouse,'draft',notes,time.time()))
 for x in lines:
  sku=str(x.get('sku','')).strip();q=float(x.get('quantity',0))
  if not sku or q<=0:c.rollback();c.close();raise HTTPException(400,'Invalid transfer line')
  c.execute('INSERT INTO warehouse_transfer_lines(id,transfer_id,sku,requested_qty) VALUES(?,?,?,?)',(str(uuid.uuid4()),i,sku,q))
 c.commit();c.close();return {'id':i,'transfer_no':n,'status':'draft'}
@router.post('/warehouse/transfers/{transfer_id}/ship')
def ship(transfer_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();t=c.execute('SELECT * FROM warehouse_transfer_orders WHERE id=?',(transfer_id,)).fetchone()
 if not t:c.close();raise HTTPException(404,'Transfer not found')
 if t['status']!='draft':c.close();raise HTTPException(400,'Only draft transfers can ship')
 lines=c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(transfer_id,)).fetchall()
 for l in lines:
  if stock(c,l['sku'],t['from_warehouse'])<float(l['requested_qty']):c.rollback();c.close();raise HTTPException(400,f'Insufficient stock for {l["sku"]}')
 for l in lines:change(c,l['sku'],t['from_warehouse'],-float(l['requested_qty']));c.execute('UPDATE warehouse_transfer_lines SET shipped_qty=requested_qty WHERE id=?',(l['id'],))
 c.execute("UPDATE warehouse_transfer_orders SET status='in_transit',shipped_at=? WHERE id=?",(time.time(),transfer_id));c.commit();c.close();return {'transfer_id':transfer_id,'status':'in_transit'}
@router.post('/warehouse/transfers/{transfer_id}/receive')
def receive(transfer_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();t=c.execute('SELECT * FROM warehouse_transfer_orders WHERE id=?',(transfer_id,)).fetchone()
 if not t:c.close();raise HTTPException(404,'Transfer not found')
 if t['status']!='in_transit':c.close();raise HTTPException(400,'Transfer is not in transit')
 lines=c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(transfer_id,)).fetchall()
 for l in lines:change(c,l['sku'],t['to_warehouse'],float(l['shipped_qty']));c.execute('UPDATE warehouse_transfer_lines SET received_qty=shipped_qty WHERE id=?',(l['id'],))
 c.execute("UPDATE warehouse_transfer_orders SET status='received',received_at=? WHERE id=?",(time.time(),transfer_id));c.commit();c.close();return {'transfer_id':transfer_id,'status':'received'}
@router.get('/warehouse/transfers')
def transfers(warehouse_id:str=Query(''),status:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT * FROM warehouse_transfer_orders WHERE 1=1';a=[]
 if warehouse_id:q+=' AND (from_warehouse=? OR to_warehouse=?)';a += [warehouse_id,warehouse_id]
 if status:q+=' AND status=?';a.append(status)
 q+=' ORDER BY created_at DESC';rows=[dict(r) for r in c.execute(q,a).fetchall()]
 for t in rows:t['lines']=[dict(x) for x in c.execute('SELECT * FROM warehouse_transfer_lines WHERE transfer_id=?',(t['id'],)).fetchall()]
 c.close();return {'results':rows}
@router.get('/warehouse/network-balance')
def balance(x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();rules=c.execute('SELECT * FROM warehouse_reorder_rules WHERE enabled=1 ORDER BY sku,warehouse_id').fetchall();suggest=[]
 by={}
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

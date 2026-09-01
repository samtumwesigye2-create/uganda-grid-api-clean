import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter();ROLES={'warehouse_associate','picker','packer','receiver','inventory_controller','forklift_operator','dispatcher','quality_inspector','supervisor','warehouse_manager','security'};TASK_TYPES={'receiving','putaway','picking','packing','dispatch','cycle_count','stock_audit','transfer','quality','returns','replenishment','maintenance','safety','other'}
def db():c=sqlite3.connect(DB,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');return c
def init():
 c=db();c.execute('BEGIN IMMEDIATE');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_staff(id TEXT PRIMARY KEY,employee_no TEXT UNIQUE NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',phone TEXT,status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_shifts(id TEXT PRIMARY KEY,staff_id TEXT NOT NULL,shift_date TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'scheduled',clock_in REAL,clock_out REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_scanners(id TEXT PRIMARY KEY,scanner_code TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',assigned_staff_id TEXT,status TEXT NOT NULL DEFAULT 'available',battery_level REAL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_tasks(id TEXT PRIMARY KEY,task_no TEXT UNIQUE NOT NULL,task_type TEXT NOT NULL,title TEXT NOT NULL,staff_id TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',reference_no TEXT,priority INTEGER NOT NULL DEFAULT 100,status TEXT NOT NULL DEFAULT 'assigned',quantity REAL NOT NULL DEFAULT 0,created_at REAL NOT NULL,started_at REAL,completed_at REAL,note TEXT)''');c.execute('CREATE INDEX IF NOT EXISTS idx_wstaff ON warehouse_staff(warehouse_id,status)');c.execute('CREATE INDEX IF NOT EXISTS idx_wtasks ON warehouse_tasks(warehouse_id,status,priority)');c.execute('CREATE INDEX IF NOT EXISTS idx_shift_staff ON warehouse_shifts(staff_id,shift_date,status)');c.execute('COMMIT');c.close()
init()
def auth(k,p):require_permission(k,p)
def no():return f'TASK-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
def staff_ok(c,sid,w=None):
 s=c.execute("SELECT * FROM warehouse_staff WHERE id=? AND status='active'",(sid,)).fetchone()
 if not s:raise HTTPException(404,'Active staff member not found')
 if w and s['warehouse_id']!=w:raise HTTPException(409,'Staff member belongs to another warehouse')
 return s
def active_shift(c,sid):return c.execute("SELECT * FROM warehouse_shifts WHERE staff_id=? AND status='active' AND clock_out IS NULL ORDER BY clock_in DESC LIMIT 1",(sid,)).fetchone()
@router.post('/warehouse/staff')
def add_staff(employee_no:str=Form(...),name:str=Form(...),role:str=Form('warehouse_associate'),warehouse_id:str=Form('main'),phone:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');role=role.strip().lower()
 if role not in ROLES:raise HTTPException(400,'Invalid warehouse role')
 c=db();c.execute('BEGIN IMMEDIATE');i=str(uuid.uuid4())
 try:c.execute('INSERT INTO warehouse_staff VALUES(?,?,?,?,?,?,?,?)',(i,employee_no.upper(),name,role,warehouse_id,phone,'active',time.time()));c.execute('COMMIT');r=dict(c.execute('SELECT * FROM warehouse_staff WHERE id=?',(i,)).fetchone());return r
 except sqlite3.IntegrityError:c.execute('ROLLBACK');raise HTTPException(409,'Employee number already exists')
 finally:c.close()
@router.get('/warehouse/staff')
def staff(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute("SELECT * FROM warehouse_staff WHERE warehouse_id=? AND status='active' ORDER BY role,name",(warehouse_id,)).fetchall()];c.close();return {'count':len(r),'roles':sorted(ROLES),'results':r}
@router.post('/warehouse/staff/{staff_id}/shift')
def shift(staff_id:str,shift_date:str=Form(...),start_time:str=Form(...),end_time:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write')
 if start_time>=end_time:raise HTTPException(400,'Shift end must be after shift start')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  staff_ok(c,staff_id);over=c.execute("SELECT 1 FROM warehouse_shifts WHERE staff_id=? AND shift_date=? AND status NOT IN ('cancelled') AND NOT(end_time<=? OR start_time>=?) LIMIT 1",(staff_id,shift_date,start_time,end_time)).fetchone()
  if over:raise HTTPException(409,'Shift overlaps an existing shift')
  i=str(uuid.uuid4());c.execute('INSERT INTO warehouse_shifts(id,staff_id,shift_date,start_time,end_time) VALUES(?,?,?,?,?)',(i,staff_id,shift_date,start_time,end_time));c.execute('COMMIT');return dict(c.execute('SELECT * FROM warehouse_shifts WHERE id=?',(i,)).fetchone())
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/shifts')
def shifts(warehouse_id:str=Query('main'),shift_date:str=Query(''),status:str=Query(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();q='SELECT sh.*,s.name,s.employee_no,s.role FROM warehouse_shifts sh JOIN warehouse_staff s ON s.id=sh.staff_id WHERE s.warehouse_id=?';a=[warehouse_id]
 if shift_date:q+=' AND sh.shift_date=?';a.append(shift_date)
 if status:q+=' AND sh.status=?';a.append(status)
 q+=' ORDER BY sh.shift_date DESC,sh.start_time';r=[dict(x) for x in c.execute(q,a).fetchall()];c.close();return {'results':r}
@router.post('/warehouse/shifts/{shift_id}/clock')
def clock(shift_id:str,action:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  s=c.execute('SELECT * FROM warehouse_shifts WHERE id=?',(shift_id,)).fetchone()
  if not s:raise HTTPException(404,'Shift not found')
  staff_ok(c,s['staff_id']);now=time.time()
  if action=='in':
   if s['status']!='scheduled' or s['clock_in']:raise HTTPException(409,'Shift cannot be clocked in from its current state')
   if active_shift(c,s['staff_id']):raise HTTPException(409,'Staff member already has an active shift')
   c.execute("UPDATE warehouse_shifts SET clock_in=?,status='active' WHERE id=?",(now,shift_id));status='active'
  elif action=='out':
   if s['status']!='active' or not s['clock_in'] or s['clock_out']:raise HTTPException(409,'Only an active shift can be clocked out')
   c.execute("UPDATE warehouse_shifts SET clock_out=?,status='completed' WHERE id=?",(now,shift_id));c.execute("UPDATE warehouse_scanners SET assigned_staff_id=NULL,status='available',updated_at=? WHERE assigned_staff_id=?",(now,s['staff_id']));status='completed'
  else:raise HTTPException(400,'Action must be in or out')
  c.execute('COMMIT');return {'shift_id':shift_id,'status':status}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/scanners')
def scanner(scanner_code:str=Form(...),warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE');i=str(uuid.uuid4())
 try:c.execute('INSERT INTO warehouse_scanners VALUES(?,?,?,?,?,?,?)',(i,scanner_code.upper(),warehouse_id,None,'available',None,time.time()));c.execute('COMMIT');return {'id':i,'scanner_code':scanner_code.upper(),'status':'available'}
 except sqlite3.IntegrityError:c.execute('ROLLBACK');raise HTTPException(409,'Scanner already exists')
 finally:c.close()
@router.post('/warehouse/scanners/{scanner_id}/assign')
def assign_scanner(scanner_id:str,staff_id:str=Form(...),battery_level:float=Form(100),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE')
 try:
  sc=c.execute('SELECT * FROM warehouse_scanners WHERE id=?',(scanner_id,)).fetchone()
  if not sc:raise HTTPException(404,'Scanner not found')
  if sc['status']!='available' or sc['assigned_staff_id']:raise HTTPException(409,'Scanner is already assigned')
  staff_ok(c,staff_id,sc['warehouse_id'])
  if not active_shift(c,staff_id):raise HTTPException(409,'Staff member must be clocked into an active shift')
  other=c.execute("SELECT 1 FROM warehouse_scanners WHERE assigned_staff_id=? AND status='assigned'",(staff_id,)).fetchone()
  if other:raise HTTPException(409,'Staff member already has an assigned scanner')
  c.execute("UPDATE warehouse_scanners SET assigned_staff_id=?,status='assigned',battery_level=?,updated_at=? WHERE id=?",(staff_id,max(0,min(100,battery_level)),time.time(),scanner_id));c.execute('COMMIT');return {'scanner_id':scanner_id,'staff_id':staff_id,'status':'assigned'}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/scanners/{scanner_id}/release')
def release_scanner(scanner_id:str,x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute('BEGIN IMMEDIATE');sc=c.execute('SELECT * FROM warehouse_scanners WHERE id=?',(scanner_id,)).fetchone()
 if not sc:c.execute('ROLLBACK');c.close();raise HTTPException(404,'Scanner not found')
 c.execute("UPDATE warehouse_scanners SET assigned_staff_id=NULL,status='available',updated_at=? WHERE id=?",(time.time(),scanner_id));c.execute('COMMIT');c.close();return {'scanner_id':scanner_id,'status':'available'}
@router.post('/warehouse/tasks')
def task(task_type:str=Form(...),title:str=Form(...),staff_id:str=Form(''),warehouse_id:str=Form('main'),reference_no:str=Form(''),priority:int=Form(100),quantity:float=Form(0),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');task_type=task_type.strip().lower()
 if task_type not in TASK_TYPES:raise HTTPException(400,'Invalid warehouse task type')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  if staff_id:staff_ok(c,staff_id,warehouse_id)
  i=str(uuid.uuid4());tn=no();c.execute('INSERT INTO warehouse_tasks(id,task_no,task_type,title,staff_id,warehouse_id,reference_no,priority,status,quantity,created_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(i,tn,task_type,title,staff_id or None,warehouse_id,reference_no,priority,'assigned',quantity,time.time(),note));c.execute('COMMIT');return {'id':i,'task_no':tn,'status':'assigned'}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.post('/warehouse/tasks/{task_id}/status')
def task_status(task_id:str,status:str=Form(...),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');transitions={'assigned':{'in_progress','blocked','cancelled'},'blocked':{'assigned','cancelled'},'in_progress':{'completed','blocked'},'completed':set(),'cancelled':set()}
 if status not in set(transitions):raise HTTPException(400,'Invalid task status')
 c=db();c.execute('BEGIN IMMEDIATE')
 try:
  t=c.execute('SELECT * FROM warehouse_tasks WHERE id=?',(task_id,)).fetchone()
  if not t:raise HTTPException(404,'Task not found')
  if status not in transitions.get(t['status'],set()):raise HTTPException(409,f'Invalid task transition: {t["status"]} → {status}')
  if status=='in_progress':
   if not t['staff_id']:raise HTTPException(409,'Task must be assigned to staff before starting')
   staff_ok(c,t['staff_id'],t['warehouse_id'])
   if not active_shift(c,t['staff_id']):raise HTTPException(409,'Assigned staff member is not clocked in')
  now=time.time();c.execute('UPDATE warehouse_tasks SET status=?,note=?,started_at=CASE WHEN ?="in_progress" AND started_at IS NULL THEN ? ELSE started_at END,completed_at=CASE WHEN ?="completed" THEN ? ELSE completed_at END WHERE id=?',(status,note,status,now,status,now,task_id));c.execute('COMMIT');return {'task_id':task_id,'status':status}
 except Exception:c.execute('ROLLBACK');raise
 finally:c.close()
@router.get('/warehouse/staff/dashboard')
def dashboard(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();people=[dict(x) for x in c.execute("SELECT * FROM warehouse_staff WHERE warehouse_id=? AND status='active' ORDER BY name",(warehouse_id,)).fetchall()];tasks=[dict(x) for x in c.execute("SELECT t.*,s.name staff_name FROM warehouse_tasks t LEFT JOIN warehouse_staff s ON s.id=t.staff_id WHERE t.warehouse_id=? AND t.status NOT IN ('cancelled') ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'assigned' THEN 1 ELSE 2 END,t.priority,t.created_at DESC LIMIT 100",(warehouse_id,)).fetchall()];scanners=[dict(x) for x in c.execute("SELECT sc.*,s.name staff_name FROM warehouse_scanners sc LEFT JOIN warehouse_staff s ON s.id=sc.assigned_staff_id WHERE sc.warehouse_id=? ORDER BY sc.scanner_code",(warehouse_id,)).fetchall()];active=[dict(x) for x in c.execute("SELECT sh.*,s.name,s.role FROM warehouse_shifts sh JOIN warehouse_staff s ON s.id=sh.staff_id WHERE s.warehouse_id=? AND sh.status='active' ORDER BY sh.clock_in",(warehouse_id,)).fetchall()];prod=[]
 for p in people:
  r=c.execute("SELECT COUNT(*) completed,COALESCE(SUM(quantity),0) qty,COALESCE(AVG(completed_at-started_at),0) avg_seconds FROM warehouse_tasks WHERE staff_id=? AND status='completed' AND completed_at>=?",(p['id'],time.time()-86400)).fetchone();prod.append({'staff_id':p['id'],'name':p['name'],'role':p['role'],'completed_today':r['completed'],'quantity_today':r['qty'],'avg_task_seconds':round(float(r['avg_seconds'] or 0),1)})
 c.close();return {'staff':people,'active_shifts':active,'tasks':tasks,'scanners':scanners,'productivity':prod,'roles':sorted(ROLES),'task_types':sorted(TASK_TYPES)}

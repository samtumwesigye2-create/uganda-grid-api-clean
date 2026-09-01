import os,sqlite3,time,uuid
from fastapi import APIRouter,Form,Header,HTTPException,Query
from auth import require_permission
BASE=os.path.dirname(os.path.abspath(__file__));DB=os.path.join(BASE,'data_hub.db');router=APIRouter()
def db():c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 c=db();c.execute('''CREATE TABLE IF NOT EXISTS warehouse_staff(id TEXT PRIMARY KEY,employee_no TEXT UNIQUE NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',phone TEXT,status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_shifts(id TEXT PRIMARY KEY,staff_id TEXT NOT NULL,shift_date TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'scheduled',clock_in REAL,clock_out REAL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_scanners(id TEXT PRIMARY KEY,scanner_code TEXT UNIQUE NOT NULL,warehouse_id TEXT NOT NULL DEFAULT 'main',assigned_staff_id TEXT,status TEXT NOT NULL DEFAULT 'available',battery_level REAL,updated_at REAL NOT NULL)''');c.execute('''CREATE TABLE IF NOT EXISTS warehouse_tasks(id TEXT PRIMARY KEY,task_no TEXT UNIQUE NOT NULL,task_type TEXT NOT NULL,title TEXT NOT NULL,staff_id TEXT,warehouse_id TEXT NOT NULL DEFAULT 'main',reference_no TEXT,priority INTEGER NOT NULL DEFAULT 100,status TEXT NOT NULL DEFAULT 'assigned',quantity REAL NOT NULL DEFAULT 0,created_at REAL NOT NULL,started_at REAL,completed_at REAL,note TEXT)''');c.execute('CREATE INDEX IF NOT EXISTS idx_wstaff ON warehouse_staff(warehouse_id,status)');c.execute('CREATE INDEX IF NOT EXISTS idx_wtasks ON warehouse_tasks(warehouse_id,status,priority)');c.commit();c.close()
init()
def auth(k,p):require_permission(k,p)
def no():return f'TASK-{time.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'
@router.post('/warehouse/staff')
def add_staff(employee_no:str=Form(...),name:str=Form(...),role:str=Form('warehouse_associate'),warehouse_id:str=Form('main'),phone:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4())
 try:c.execute('INSERT INTO warehouse_staff VALUES(?,?,?,?,?,?,?,?)',(i,employee_no.upper(),name,role,warehouse_id,phone,'active',time.time()));c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Employee number already exists')
 r=dict(c.execute('SELECT * FROM warehouse_staff WHERE id=?',(i,)).fetchone());c.close();return r
@router.get('/warehouse/staff')
def staff(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();r=[dict(x) for x in c.execute("SELECT * FROM warehouse_staff WHERE warehouse_id=? AND status='active' ORDER BY role,name",(warehouse_id,)).fetchall()];c.close();return {'count':len(r),'results':r}
@router.post('/warehouse/staff/{staff_id}/shift')
def shift(staff_id:str,shift_date:str=Form(...),start_time:str=Form(...),end_time:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();s=c.execute('SELECT id FROM warehouse_staff WHERE id=?',(staff_id,)).fetchone()
 if not s:c.close();raise HTTPException(404,'Staff member not found')
 i=str(uuid.uuid4());c.execute('INSERT INTO warehouse_shifts(id,staff_id,shift_date,start_time,end_time) VALUES(?,?,?,?,?)',(i,staff_id,shift_date,start_time,end_time));c.commit();r=dict(c.execute('SELECT * FROM warehouse_shifts WHERE id=?',(i,)).fetchone());c.close();return r
@router.post('/warehouse/shifts/{shift_id}/clock')
def clock(shift_id:str,action:str=Form(...),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();s=c.execute('SELECT * FROM warehouse_shifts WHERE id=?',(shift_id,)).fetchone()
 if not s:c.close();raise HTTPException(404,'Shift not found')
 now=time.time()
 if action=='in':c.execute("UPDATE warehouse_shifts SET clock_in=?,status='active' WHERE id=?",(now,shift_id))
 elif action=='out':c.execute("UPDATE warehouse_shifts SET clock_out=?,status='completed' WHERE id=?",(now,shift_id))
 else:c.close();raise HTTPException(400,'Action must be in or out')
 c.commit();c.close();return {'shift_id':shift_id,'status':'active' if action=='in' else 'completed'}
@router.post('/warehouse/scanners')
def scanner(scanner_code:str=Form(...),warehouse_id:str=Form('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4())
 try:c.execute('INSERT INTO warehouse_scanners VALUES(?,?,?,?,?,?,?)',(i,scanner_code.upper(),warehouse_id,None,'available',None,time.time()));c.commit()
 except sqlite3.IntegrityError:c.close();raise HTTPException(409,'Scanner already exists')
 c.close();return {'id':i,'scanner_code':scanner_code.upper(),'status':'available'}
@router.post('/warehouse/scanners/{scanner_id}/assign')
def assign_scanner(scanner_id:str,staff_id:str=Form(...),battery_level:float=Form(100),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();c.execute("UPDATE warehouse_scanners SET assigned_staff_id=?,status='assigned',battery_level=?,updated_at=? WHERE id=?",(staff_id,battery_level,time.time(),scanner_id));c.commit();c.close();return {'scanner_id':scanner_id,'staff_id':staff_id,'status':'assigned'}
@router.post('/warehouse/tasks')
def task(task_type:str=Form(...),title:str=Form(...),staff_id:str=Form(''),warehouse_id:str=Form('main'),reference_no:str=Form(''),priority:int=Form(100),quantity:float=Form(0),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');c=db();i=str(uuid.uuid4());tn=no();c.execute('INSERT INTO warehouse_tasks(id,task_no,task_type,title,staff_id,warehouse_id,reference_no,priority,status,quantity,created_at,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(i,tn,task_type,title,staff_id or None,warehouse_id,reference_no,priority,'assigned',quantity,time.time(),note));c.commit();c.close();return {'id':i,'task_no':tn,'status':'assigned'}
@router.post('/warehouse/tasks/{task_id}/status')
def task_status(task_id:str,status:str=Form(...),note:str=Form(''),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:write');allowed={'assigned','in_progress','completed','blocked','cancelled'}
 if status not in allowed:raise HTTPException(400,'Invalid task status')
 c=db();t=c.execute('SELECT * FROM warehouse_tasks WHERE id=?',(task_id,)).fetchone()
 if not t:c.close();raise HTTPException(404,'Task not found')
 now=time.time();extra='';args=[]
 if status=='in_progress':extra=',started_at=?';args.append(now)
 if status=='completed':extra=',completed_at=?';args.append(now)
 c.execute('UPDATE warehouse_tasks SET status=?,note=?'+extra+' WHERE id=?',[status,note]+args+[task_id]);c.commit();c.close();return {'task_id':task_id,'status':status}
@router.get('/warehouse/staff/dashboard')
def dashboard(warehouse_id:str=Query('main'),x_access_code:str=Header(default='')):
 auth(x_access_code,'inventory:read');c=db();people=[dict(x) for x in c.execute("SELECT * FROM warehouse_staff WHERE warehouse_id=? AND status='active' ORDER BY name",(warehouse_id,)).fetchall()];tasks=[dict(x) for x in c.execute("SELECT t.*,s.name staff_name FROM warehouse_tasks t LEFT JOIN warehouse_staff s ON s.id=t.staff_id WHERE t.warehouse_id=? AND t.status NOT IN ('cancelled') ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'assigned' THEN 1 ELSE 2 END,t.priority,t.created_at DESC LIMIT 100",(warehouse_id,)).fetchall()];scanners=[dict(x) for x in c.execute("SELECT sc.*,s.name staff_name FROM warehouse_scanners sc LEFT JOIN warehouse_staff s ON s.id=sc.assigned_staff_id WHERE sc.warehouse_id=? ORDER BY sc.scanner_code",(warehouse_id,)).fetchall()];prod=[]
 for p in people:
  r=c.execute("SELECT COUNT(*) completed,COALESCE(SUM(quantity),0) qty,COALESCE(AVG(completed_at-started_at),0) avg_seconds FROM warehouse_tasks WHERE staff_id=? AND status='completed' AND completed_at>=?",(p['id'],time.time()-86400)).fetchone();prod.append({'staff_id':p['id'],'name':p['name'],'role':p['role'],'completed_today':r['completed'],'quantity_today':r['qty'],'avg_task_seconds':round(float(r['avg_seconds'] or 0),1)})
 c.close();return {'staff':people,'tasks':tasks,'scanners':scanners,'productivity':prod}

from __future__ import annotations
import json,os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from ugaforce_hr.security import current_user
DATABASE_URL=os.getenv('UGAFORCE_HR_DATABASE_URL') or os.getenv('DATABASE_URL')
router=APIRouter(prefix='/api/v1',tags=['UGAFORCE-HR Completion'])
HR={'HR_SPECIALIST','HR_MANAGER','HR_ADMIN'}
def db():
 if not DATABASE_URL: raise HTTPException(503,'HR database is not configured')
 return psycopg2.connect(DATABASE_URL,connect_timeout=5)
def emit(c,t,p): c.execute('insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)',(t,json.dumps(p,default=str)))
class Notice(BaseModel): employee_id:str; subject:str; body:str; channel:str='in_app'
class Offboard(BaseModel): employee_id:str; last_working_date:str; reason:str=''
class TaskDecision(BaseModel): notes:str=''
@router.post('/notifications')
def notify(p:Notice,u:dict=Depends(current_user)):
 if u.get('role') not in HR: raise HTTPException(403,'HR authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("insert into ugaforce_hr_notifications(employee_id,channel,subject,body,status) values(%s,%s,%s,%s,'queued') returning id::text,employee_id::text,channel,subject,status,created_at",(p.employee_id,p.channel,p.subject,p.body)); r=dict(c.fetchone()); emit(c,'notification.queued',r)
  cn.commit(); return r
@router.get('/notifications/me')
def my_notifications(u:dict=Depends(current_user)):
 if not u.get('employee_id'): raise HTTPException(403,'Employee-linked account required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c: c.execute('select id::text,channel,subject,body,status,created_at,sent_at,read_at from ugaforce_hr_notifications where employee_id=%s order by created_at desc limit 100',(u['employee_id'],)); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/offboarding')
def start(p:Offboard,u:dict=Depends(current_user)):
 if u.get('role') not in HR: raise HTTPException(403,'HR authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("insert into ugaforce_hr_offboarding_cases(employee_id,last_working_date,reason,started_by) values(%s,%s,%s,%s) returning id::text,employee_id::text,last_working_date,status,started_at",(p.employee_id,p.last_working_date,p.reason,u.get('employee_id'))); r=dict(c.fetchone())
   for title,owner in [('Manager handover and knowledge transfer','MANAGER'),('Return company equipment','HR_SPECIALIST'),('Disable system access','HR_ADMIN'),('Final payroll and benefits clearance','HR_MANAGER'),('Exit interview','HR_SPECIALIST')]: c.execute('insert into ugaforce_hr_offboarding_tasks(case_id,title,owner_role,due_date) values(%s,%s,%s,%s)',(r['id'],title,owner,p.last_working_date))
   emit(c,'offboarding.started',r)
  cn.commit(); return r
@router.get('/offboarding')
def cases(u:dict=Depends(current_user)):
 if u.get('role') not in HR: raise HTTPException(403,'HR authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c: c.execute('select o.id::text,o.employee_id::text,e.employee_number,e.first_name,e.last_name,o.last_working_date,o.reason,o.status,o.started_at,o.completed_at from ugaforce_hr_offboarding_cases o join ugaforce_hr_employees e on e.id=o.employee_id order by o.started_at desc'); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/offboarding/tasks/{tid}/complete')
def complete_task(tid:str,p:TaskDecision,u:dict=Depends(current_user)):
 if u.get('role') not in {'MANAGER'}|HR: raise HTTPException(403,'Clearance authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("update ugaforce_hr_offboarding_tasks set status='done',completed_at=now(),notes=%s where id=%s and status<>'done' returning id::text,case_id::text,title,status",(p.notes,tid)); r=c.fetchone()
   if not r: raise HTTPException(409,'Task already completed or not found')
   r=dict(r); c.execute("select count(*) from ugaforce_hr_offboarding_tasks where case_id=%s and status<>'done'",(r['case_id'],)); remaining=c.fetchone()[0]
   if remaining==0:
    c.execute("update ugaforce_hr_offboarding_cases set status='completed',completed_at=now() where id=%s returning employee_id::text",(r['case_id'],)); emp=c.fetchone()['employee_id']; c.execute("update ugaforce_hr_employees set employment_status='inactive' where id=%s",(emp,)); emit(c,'offboarding.completed',{'case_id':r['case_id'],'employee_id':emp})
  cn.commit(); return {'task':r,'remaining_tasks':remaining}
@router.get('/security/readiness')
def readiness(u:dict=Depends(current_user)):
 if u.get('role')!='HR_ADMIN': raise HTTPException(403,'HR administrator authority required')
 checks={'database_configured':bool(DATABASE_URL),'bootstrap_key_configured':bool(os.getenv('UGAFORCE_HR_BOOTSTRAP_KEY')),'cors_configured':bool(os.getenv('UGAFORCE_HR_ALLOWED_ORIGINS')),'ugacore_configured':bool(os.getenv('UGACORE_URL') and os.getenv('UGACORE_SERVICE_KEY'))}
 return {'ready':all([checks['database_configured'],checks['bootstrap_key_configured'],checks['cors_configured']]),'checks':checks,'note':'External integrations remain fail-open; production deployment and migration execution must be verified separately.'}
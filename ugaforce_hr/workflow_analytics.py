from __future__ import annotations
import json,os
from datetime import datetime,timezone
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from ugaforce_hr.security import current_user
DATABASE_URL=os.getenv('UGAFORCE_HR_DATABASE_URL') or os.getenv('DATABASE_URL')
router=APIRouter(prefix='/api/v1',tags=['UGAFORCE-HR Workflow & Analytics'])
HR={'HR_SPECIALIST','HR_MANAGER','HR_ADMIN'}
def db():
 if not DATABASE_URL: raise HTTPException(503,'HR database is not configured')
 return psycopg2.connect(DATABASE_URL,connect_timeout=5)
def emit(c,t,p): c.execute('insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)',(t,json.dumps(p,default=str)))
class WorkflowIn(BaseModel): name:str; resource_type:str; approver_roles:list[str]; sla_hours:int=Field(default=48,ge=1)
class ApprovalIn(BaseModel): workflow_id:Optional[str]=None; resource_type:str; resource_id:str
class Decision(BaseModel): action:str; comments:Optional[str]=None
@router.post('/workflows')
def workflow(p:WorkflowIn,u:dict=Depends(current_user)):
 if u.get('role') not in {'HR_MANAGER','HR_ADMIN'}: raise HTTPException(403,'HR manager authority required')
 if not p.approver_roles: raise HTTPException(400,'At least one approver role is required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('insert into ugaforce_hr_workflow_definitions(name,resource_type,sla_hours) values(%s,%s,%s) returning id::text,name,resource_type,sla_hours,is_active',(p.name,p.resource_type,p.sla_hours)); r=dict(c.fetchone())
   for i,role in enumerate(p.approver_roles,1): c.execute('insert into ugaforce_hr_workflow_steps(workflow_id,step_order,approver_role) values(%s,%s,%s)',(r['id'],i,role))
   emit(c,'workflow.created',r)
  cn.commit(); return r
@router.post('/approvals')
def request(p:ApprovalIn,u:dict=Depends(current_user)):
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   wid=p.workflow_id
   if not wid:
    c.execute('select id::text,sla_hours from ugaforce_hr_workflow_definitions where resource_type=%s and is_active order by created_at desc limit 1',(p.resource_type,)); w=c.fetchone()
    if not w: raise HTTPException(409,'No active workflow configured for this resource')
    wid=w['id']; sla=w['sla_hours']
   else:
    c.execute('select sla_hours from ugaforce_hr_workflow_definitions where id=%s and is_active',(wid,)); w=c.fetchone()
    if not w: raise HTTPException(404,'Workflow not found')
    sla=w['sla_hours']
   c.execute("insert into ugaforce_hr_approval_requests(workflow_id,resource_type,resource_id,requested_by,due_at) values(%s,%s,%s,%s,now()+(%s||' hours')::interval) returning id::text,status,current_step,due_at",(wid,p.resource_type,p.resource_id,u.get('employee_id'),sla)); r=dict(c.fetchone()); emit(c,'approval.requested',{'approval_id':r['id'],'resource_type':p.resource_type,'resource_id':p.resource_id})
  cn.commit(); return r
@router.get('/approvals/inbox')
def inbox(status:str=Query(default='pending'),u:dict=Depends(current_user)):
 if u.get('role') not in {'MANAGER'}|HR: raise HTTPException(403,'Approval authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("select a.id::text,a.resource_type,a.resource_id::text,a.status,a.current_step,a.due_at,w.name workflow,s.approver_role,(a.due_at<now() and a.status='pending') overdue from ugaforce_hr_approval_requests a join ugaforce_hr_workflow_definitions w on w.id=a.workflow_id left join ugaforce_hr_workflow_steps s on s.workflow_id=a.workflow_id and s.step_order=a.current_step where (%s='' or a.status=%s) and (s.approver_role=%s or %s in ('HR_MANAGER','HR_ADMIN')) order by a.due_at nulls last",(status,status,u.get('role'),u.get('role'))); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/approvals/{aid}/decision')
def decide(aid:str,p:Decision,u:dict=Depends(current_user)):
 if p.action not in {'approve','reject'}: raise HTTPException(400,'action must be approve or reject')
 if u.get('role') not in {'MANAGER'}|HR: raise HTTPException(403,'Approval authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('select * from ugaforce_hr_approval_requests where id=%s for update',(aid,)); a=c.fetchone()
   if not a or a['status']!='pending': raise HTTPException(409,'Approval is not pending')
   c.execute('select approver_role from ugaforce_hr_workflow_steps where workflow_id=%s and step_order=%s',(a['workflow_id'],a['current_step'])); step=c.fetchone()
   if step and step['approver_role']!=u.get('role') and u.get('role') not in {'HR_MANAGER','HR_ADMIN'}: raise HTTPException(403,'Not current approver')
   c.execute('insert into ugaforce_hr_approval_actions(request_id,step_order,actor_id,action,comments) values(%s,%s,%s,%s,%s)',(aid,a['current_step'],u.get('employee_id'),p.action,p.comments))
   if p.action=='reject': status='rejected'; c.execute("update ugaforce_hr_approval_requests set status='rejected',completed_at=now() where id=%s",(aid,))
   else:
    c.execute('select 1 from ugaforce_hr_workflow_steps where workflow_id=%s and step_order>%s limit 1',(a['workflow_id'],a['current_step'])); more=c.fetchone()
    if more: status='pending'; c.execute('update ugaforce_hr_approval_requests set current_step=current_step+1 where id=%s',(aid,))
    else: status='approved'; c.execute("update ugaforce_hr_approval_requests set status='approved',completed_at=now() where id=%s",(aid,))
   emit(c,f'approval.{p.action}d',{'approval_id':aid,'status':status})
  cn.commit(); return {'id':aid,'status':status}
@router.get('/analytics/executive')
def executive(u:dict=Depends(current_user)):
 if u.get('role') not in HR: raise HTTPException(403,'HR analytics authority required')
 with db() as cn:
  with cn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("select count(*) total,count(*) filter(where employment_status='active') active from ugaforce_hr_employees"); people=dict(c.fetchone())
   c.execute("select count(*) open_jobs from ugaforce_hr_job_postings where status='published'"); recruiting=dict(c.fetchone())
   c.execute("select count(*) pending_approvals,count(*) filter(where due_at<now()) overdue_approvals from ugaforce_hr_approval_requests where status='pending'"); approvals=dict(c.fetchone())
   c.execute("select count(*) pending_reviews from ugaforce_hr_performance_reviews where status not in ('completed','closed')"); performance=dict(c.fetchone())
   c.execute("select count(*) pending_leave from ugaforce_hr_leave_requests where status='pending'"); attendance=dict(c.fetchone())
 return {'generated_at':datetime.now(timezone.utc),'people':people,'recruiting':recruiting,'approvals':approvals,'performance':performance,'attendance':attendance}

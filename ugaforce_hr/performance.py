from __future__ import annotations
import json, os
from typing import Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from ugaforce_hr.security import current_user
from ugaforce_hr.ugacore_client import mirror_audit
DATABASE_URL=os.getenv('UGAFORCE_HR_DATABASE_URL') or os.getenv('DATABASE_URL')
router=APIRouter(prefix='/api/v1/performance',tags=['UGAFORCE-HR Performance'])
HR_ROLES={'HR_SPECIALIST','HR_MANAGER','HR_ADMIN'}
def db():
 if not DATABASE_URL: raise HTTPException(503,'HR database is not configured')
 return psycopg2.connect(DATABASE_URL,connect_timeout=5)
def audit(conn,actor,action,etype,eid,payload=None):
 with conn.cursor() as c:
  c.execute('insert into ugaforce_hr_audit_log(actor_id,action,entity_type,entity_id,after_json) values(%s,%s,%s,%s,%s::jsonb)',(actor,action,etype,eid,json.dumps(payload,default=str) if payload is not None else None))
  c.execute('insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)',(f'performance.{action}',json.dumps({'entity_type':etype,'entity_id':eid},default=str)))
 mirror_audit(action,etype,eid,actor_id=actor)
def hr(user):
 if user.get('role') not in HR_ROLES: raise HTTPException(403,'HR performance authority required')
class CycleIn(BaseModel):
 name:str=Field(min_length=2,max_length=160); cycle_type:str='annual'; starts_on:str; ends_on:str
class GoalIn(BaseModel):
 employee_id:str; cycle_id:Optional[str]=None; title:str=Field(min_length=2,max_length=240); description:Optional[str]=None; weight:float=0; target_value:Optional[float]=None; unit:Optional[str]=None; due_date:Optional[str]=None
class ReviewIn(BaseModel):
 cycle_id:str; employee_id:str; manager_id:Optional[str]=None
class SelfReviewIn(BaseModel): rating:float=Field(ge=1,le=5); comments:str=''
class ManagerReviewIn(BaseModel): rating:float=Field(ge=1,le=5); comments:str=''
class CalibrationIn(BaseModel): rating:float=Field(ge=1,le=5)
class RecommendationIn(BaseModel): recommendation_type:str; proposed_job_title:Optional[str]=None; proposed_salary:Optional[float]=None; rationale:Optional[str]=None
@router.get('/metrics')
def metrics(user:dict=Depends(current_user)):
 with db() as conn:
  with conn.cursor() as c:
   c.execute("select count(*) from ugaforce_hr_review_cycles where status in ('active','open')"); cycles=c.fetchone()[0]
   c.execute("select count(*) from ugaforce_hr_performance_reviews where status not in ('completed','closed')"); pending=c.fetchone()[0]
   c.execute("select count(*) from ugaforce_hr_goals where status='active'"); goals=c.fetchone()[0]
   c.execute("select count(*) from ugaforce_hr_talent_recommendations where status='proposed'"); recs=c.fetchone()[0]
 return {'active_cycles':cycles,'reviews_pending':pending,'active_goals':goals,'talent_recommendations':recs}
@router.post('/cycles')
def create_cycle(p:CycleIn,user:dict=Depends(current_user)):
 hr(user)
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("insert into ugaforce_hr_review_cycles(name,cycle_type,starts_on,ends_on,status) values(%s,%s,%s,%s,'active') returning id::text,name,cycle_type,starts_on,ends_on,status",(p.name,p.cycle_type,p.starts_on,p.ends_on)); row=dict(c.fetchone()); audit(conn,user.get('employee_id'),'cycle_created','review_cycle',row['id'],row)
  conn.commit(); return row
@router.get('/cycles')
def cycles(user:dict=Depends(current_user)):
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c: c.execute('select id::text,name,cycle_type,starts_on,ends_on,status from ugaforce_hr_review_cycles order by starts_on desc'); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/goals')
def create_goal(p:GoalIn,user:dict=Depends(current_user)):
 if user.get('role')=='EMPLOYEE' and user.get('employee_id')!=p.employee_id: raise HTTPException(403,'Self-service goals only')
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('insert into ugaforce_hr_goals(employee_id,cycle_id,title,description,weight,target_value,unit,due_date) values(%s,%s,%s,%s,%s,%s,%s,%s) returning id::text,employee_id::text,cycle_id::text,title,weight,target_value,current_value,unit,status,due_date',(p.employee_id,p.cycle_id,p.title,p.description,p.weight,p.target_value,p.unit,p.due_date)); row=dict(c.fetchone()); audit(conn,user.get('employee_id'),'goal_created','goal',row['id'],row)
  conn.commit(); return row
@router.get('/goals')
def goals(employee_id:str=Query(default=''),user:dict=Depends(current_user)):
 if user.get('role')=='EMPLOYEE': employee_id=user.get('employee_id') or ''
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c: c.execute("select g.id::text,g.employee_id::text,e.employee_number,e.first_name,e.last_name,g.title,g.weight,g.target_value,g.current_value,g.unit,g.status,g.due_date from ugaforce_hr_goals g join ugaforce_hr_employees e on e.id=g.employee_id where (%s='' or g.employee_id=%s) order by g.due_date nulls last,g.created_at desc",(employee_id,employee_id)); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/reviews')
def create_review(p:ReviewIn,user:dict=Depends(current_user)):
 hr(user)
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('insert into ugaforce_hr_performance_reviews(cycle_id,employee_id,manager_id) values(%s,%s,%s) returning id::text,cycle_id::text,employee_id::text,manager_id::text,status',(p.cycle_id,p.employee_id,p.manager_id)); row=dict(c.fetchone()); audit(conn,user.get('employee_id'),'review_created','performance_review',row['id'],row)
  conn.commit(); return row
@router.get('/reviews')
def reviews(status:str=Query(default=''),user:dict=Depends(current_user)):
 employee=user.get('employee_id') if user.get('role')=='EMPLOYEE' else None
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("select r.id::text,r.employee_id::text,e.employee_number,e.first_name,e.last_name,cy.name cycle,r.status,r.self_rating,r.manager_rating,r.calibrated_rating from ugaforce_hr_performance_reviews r join ugaforce_hr_employees e on e.id=r.employee_id join ugaforce_hr_review_cycles cy on cy.id=r.cycle_id where (%s='' or r.status=%s) and (%s is null or r.employee_id=%s) order by r.created_at desc",(status,status,employee,employee)); rows=[dict(x) for x in c.fetchall()]
 return {'count':len(rows),'results':rows}
@router.post('/reviews/{rid}/self-review')
def self_review(rid:str,p:SelfReviewIn,user:dict=Depends(current_user)):
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('select employee_id::text from ugaforce_hr_performance_reviews where id=%s',(rid,)); x=c.fetchone()
   if not x: raise HTTPException(404,'Review not found')
   if user.get('employee_id')!=x['employee_id'] and user.get('role') not in HR_ROLES: raise HTTPException(403,'Self-review access denied')
   c.execute("update ugaforce_hr_performance_reviews set self_rating=%s,self_comments=%s,status='manager_review',submitted_at=now() where id=%s returning id::text,status,self_rating,submitted_at",(p.rating,p.comments,rid)); row=dict(c.fetchone()); audit(conn,user.get('employee_id'),'self_review_submitted','performance_review',rid,row)
  conn.commit(); return row
@router.post('/reviews/{rid}/manager-review')
def manager_review(rid:str,p:ManagerReviewIn,user:dict=Depends(current_user)):
 if user.get('role') not in {'MANAGER'}|HR_ROLES: raise HTTPException(403,'Manager authority required')
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("update ugaforce_hr_performance_reviews set manager_rating=%s,manager_comments=%s,status='calibration',manager_completed_at=now() where id=%s and status in ('manager_review','self_review') returning id::text,status,manager_rating,manager_completed_at",(p.rating,p.comments,rid)); row=c.fetchone()
   if not row: raise HTTPException(409,'Review is not ready for manager assessment')
   row=dict(row); audit(conn,user.get('employee_id'),'manager_review_completed','performance_review',rid,row)
  conn.commit(); return row
@router.post('/reviews/{rid}/calibrate')
def calibrate(rid:str,p:CalibrationIn,user:dict=Depends(current_user)):
 hr(user)
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute("update ugaforce_hr_performance_reviews set calibrated_rating=%s,status='completed',calibrated_at=now() where id=%s and status='calibration' returning id::text,status,calibrated_rating,calibrated_at",(p.rating,rid)); row=c.fetchone()
   if not row: raise HTTPException(409,'Review is not ready for calibration')
   row=dict(row); audit(conn,user.get('employee_id'),'review_calibrated','performance_review',rid,row)
  conn.commit(); return row
@router.post('/reviews/{rid}/recommendations')
def recommend(rid:str,p:RecommendationIn,user:dict=Depends(current_user)):
 if user.get('role') not in {'MANAGER'}|HR_ROLES: raise HTTPException(403,'Manager authority required')
 with db() as conn:
  with conn.cursor(cursor_factory=RealDictCursor) as c:
   c.execute('select employee_id::text from ugaforce_hr_performance_reviews where id=%s',(rid,)); r=c.fetchone()
   if not r: raise HTTPException(404,'Review not found')
   c.execute('insert into ugaforce_hr_talent_recommendations(review_id,employee_id,recommendation_type,proposed_job_title,proposed_salary,rationale,created_by) values(%s,%s,%s,%s,%s,%s,%s) returning id::text,employee_id::text,recommendation_type,proposed_job_title,proposed_salary,status,created_at',(rid,r['employee_id'],p.recommendation_type,p.proposed_job_title,p.proposed_salary,p.rationale,user.get('employee_id'))); row=dict(c.fetchone()); audit(conn,user.get('employee_id'),'recommendation_created','talent_recommendation',row['id'],row)
  conn.commit(); return row
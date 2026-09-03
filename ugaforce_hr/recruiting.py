from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ugaforce_hr.security import current_user, require_role

DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
router = APIRouter(prefix="/api/v1/recruiting", tags=["UGAFORCE-HR Recruiting"])
public_router = APIRouter(prefix="/api/v1/careers", tags=["UGAFORCE-HR Careers"])


def db() -> Any:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def emit(conn: Any, event_type: str, payload: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)",
            (event_type, json.dumps(payload, default=str)),
        )


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return value[:70] or "job"


class RequisitionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    department_id: Optional[str] = None
    hiring_manager_id: str
    headcount: int = Field(default=1, ge=1, le=500)
    employment_type: str = "full_time"
    target_pay_min: Optional[float] = None
    target_pay_max: Optional[float] = None
    justification: Optional[str] = None


class PostingCreate(BaseModel):
    requisition_id: str
    title: str = Field(min_length=2, max_length=180)
    description_md: str = Field(min_length=10)
    location: Optional[str] = None
    remote_policy: str = "onsite"
    public_slug: Optional[str] = None


class ApplicationCreate(BaseModel):
    job_posting_id: str
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=240)
    phone: Optional[str] = None
    resume_storage_key: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: str = "company_site"


class StageMove(BaseModel):
    stage_id: str
    application_status: str = "interviewing"


class OfferCreate(BaseModel):
    application_id: str
    job_title: str
    department_id: Optional[str] = None
    base_salary: float = Field(ge=0)
    bonus_target: Optional[float] = None
    equity_units: Optional[float] = None
    start_date: Optional[str] = None
    expires_at: Optional[str] = None


class OfferDecision(BaseModel):
    action: str


@router.get("/metrics")
def recruiting_metrics(user: dict[str, Any] = Depends(current_user)) -> dict[str, int]:
    require_role(user, "MANAGER")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_job_postings where status='published'")
            open_jobs = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_applications where status not in ('rejected','withdrawn','offer_declined','offer_accepted')")
            active_candidates = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_interviews where status='scheduled' and scheduled_at>=now()")
            interviews = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_offers where status in ('approved','sent')")
            open_offers = cur.fetchone()[0]
    return {"open_jobs": open_jobs, "active_candidates": active_candidates, "scheduled_interviews": interviews, "open_offers": open_offers}


@router.get("/requisitions")
def list_requisitions(status: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    sql = """select r.id::text,r.title,r.department_id::text,d.name department_name,r.hiring_manager_id::text,
        concat(m.first_name,' ',m.last_name) hiring_manager,r.headcount,r.employment_type,r.status,
        r.target_pay_min,r.target_pay_max,r.justification,r.created_at,r.approved_at
        from ugaforce_hr_job_requisitions r
        left join ugaforce_hr_departments d on d.id=r.department_id
        join ugaforce_hr_employees m on m.id=r.hiring_manager_id"""
    args: list[Any] = []
    if status.strip():
        sql += " where r.status=%s"; args.append(status.strip())
    sql += " order by r.created_at desc"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args); rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/requisitions")
def create_requisition(payload: RequisitionCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    if payload.target_pay_min is not None and payload.target_pay_max is not None and payload.target_pay_min > payload.target_pay_max:
        raise HTTPException(status_code=400, detail="target_pay_min cannot exceed target_pay_max")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select 1 from ugaforce_hr_employees where id=%s and employment_status='active'", (payload.hiring_manager_id,))
            if not cur.fetchone(): raise HTTPException(status_code=400, detail="Hiring manager is not an active employee")
            cur.execute("""insert into ugaforce_hr_job_requisitions(title,department_id,hiring_manager_id,headcount,employment_type,target_pay_min,target_pay_max,justification,requested_by)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id::text,title,status,headcount,employment_type,created_at""",
                (payload.title.strip(),payload.department_id,payload.hiring_manager_id,payload.headcount,payload.employment_type,payload.target_pay_min,payload.target_pay_max,payload.justification,user.get("employee_id")))
            row = dict(cur.fetchone())
            emit(conn,"requisition.created",{"requisition_id":row["id"],"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@router.post("/requisitions/{requisition_id}/approve")
def approve_requisition(requisition_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_MANAGER")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("update ugaforce_hr_job_requisitions set status='approved',approved_at=now() where id=%s and status in ('draft','pending_approval') returning id::text,title,status,approved_at", (requisition_id,))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=409, detail="Requisition cannot be approved from its current state")
            row = dict(row); emit(conn,"requisition.approved",{"requisition_id":requisition_id,"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@router.get("/postings")
def list_postings(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select p.id::text,p.requisition_id::text,p.title,p.location,p.remote_policy,p.status,p.public_slug,p.published_at,p.closed_at,p.created_at,
                d.name department_name from ugaforce_hr_job_postings p join ugaforce_hr_job_requisitions r on r.id=p.requisition_id left join ugaforce_hr_departments d on d.id=r.department_id order by p.created_at desc""")
            rows=[dict(r) for r in cur.fetchall()]
    return {"count":len(rows),"results":rows}


@router.post("/postings")
def create_posting(payload: PostingCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select status from ugaforce_hr_job_requisitions where id=%s", (payload.requisition_id,)); req=cur.fetchone()
            if not req: raise HTTPException(status_code=404, detail="Requisition not found")
            if req["status"] != "approved": raise HTTPException(status_code=409, detail="Requisition must be approved before posting")
            base = slugify(payload.public_slug or payload.title)
            public_slug = base
            suffix = 2
            while True:
                cur.execute("select 1 from ugaforce_hr_job_postings where public_slug=%s", (public_slug,))
                if not cur.fetchone(): break
                public_slug=f"{base}-{suffix}"; suffix+=1
            cur.execute("""insert into ugaforce_hr_job_postings(requisition_id,title,description_md,location,remote_policy,public_slug)
                values(%s,%s,%s,%s,%s,%s) returning id::text,requisition_id::text,title,status,public_slug,created_at""",
                (payload.requisition_id,payload.title.strip(),payload.description_md,payload.location,payload.remote_policy,public_slug))
            row=dict(cur.fetchone())
            for order,name,kind in [(1,'Resume Screen','screen'),(2,'Interview','interview'),(3,'Final Review','interview'),(4,'Offer','offer')]:
                cur.execute("insert into ugaforce_hr_pipeline_stages(job_posting_id,name,stage_order,stage_type) values(%s,%s,%s,%s)", (row["id"],name,order,kind))
            emit(conn,"job_posting.created",{"job_posting_id":row["id"],"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@router.post("/postings/{posting_id}/publish")
def publish_posting(posting_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("update ugaforce_hr_job_postings set status='published',published_at=coalesce(published_at,now()),closed_at=null where id=%s and status in ('draft','paused') returning id::text,title,status,public_slug,published_at", (posting_id,))
            row=cur.fetchone()
            if not row: raise HTTPException(status_code=409, detail="Posting cannot be published from its current state")
            row=dict(row); emit(conn,"job_posting.published",{"job_posting_id":posting_id,"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@public_router.get("/jobs")
def public_jobs() -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select p.id::text,p.title,p.description_md,p.location,p.remote_policy,p.public_slug,p.published_at,d.name department_name
                from ugaforce_hr_job_postings p join ugaforce_hr_job_requisitions r on r.id=p.requisition_id left join ugaforce_hr_departments d on d.id=r.department_id
                where p.status='published' order by p.published_at desc""")
            rows=[dict(r) for r in cur.fetchall()]
    return {"count":len(rows),"results":rows}


@public_router.post("/apply")
def apply(payload: ApplicationCreate) -> dict[str, Any]:
    email=payload.email.strip().lower()
    with db() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("select id::text,status from ugaforce_hr_job_postings where id=%s", (payload.job_posting_id,)); posting=cur.fetchone()
                if not posting or posting["status"]!='published': raise HTTPException(status_code=404, detail="Published job not found")
                cur.execute("select id::text from ugaforce_hr_candidates where lower(email)=lower(%s)", (email,)); candidate=cur.fetchone()
                if candidate:
                    candidate_id=candidate["id"]
                    cur.execute("update ugaforce_hr_candidates set first_name=%s,last_name=%s,phone=coalesce(%s,phone),resume_storage_key=coalesce(%s,resume_storage_key),linkedin_url=coalesce(%s,linkedin_url),source=coalesce(%s,source),updated_at=now() where id=%s", (payload.first_name.strip(),payload.last_name.strip(),payload.phone,payload.resume_storage_key,payload.linkedin_url,payload.source,candidate_id))
                else:
                    cur.execute("insert into ugaforce_hr_candidates(first_name,last_name,email,phone,resume_storage_key,linkedin_url,source) values(%s,%s,%s,%s,%s,%s,%s) returning id::text", (payload.first_name.strip(),payload.last_name.strip(),email,payload.phone,payload.resume_storage_key,payload.linkedin_url,payload.source)); candidate_id=cur.fetchone()["id"]
                cur.execute("select id::text from ugaforce_hr_pipeline_stages where job_posting_id=%s order by stage_order limit 1", (payload.job_posting_id,)); stage=cur.fetchone(); stage_id=stage["id"] if stage else None
                cur.execute("insert into ugaforce_hr_applications(candidate_id,job_posting_id,current_stage_id) values(%s,%s,%s) returning id::text,status,applied_at", (candidate_id,payload.job_posting_id,stage_id)); application=dict(cur.fetchone())
                if stage_id:
                    cur.execute("insert into ugaforce_hr_application_stage_history(application_id,stage_id) values(%s,%s)", (application["id"],stage_id))
                emit(conn,"application.received",{"application_id":application["id"],"candidate_id":candidate_id,"job_posting_id":payload.job_posting_id})
            conn.commit()
            return {"application_id":application["id"],"status":application["status"],"applied_at":application["applied_at"]}
        except psycopg2.errors.UniqueViolation:
            conn.rollback(); raise HTTPException(status_code=409, detail="Candidate has already applied for this job")


@router.get("/applications")
def applications(posting_id: str = Query(default=""), status: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user,"MANAGER")
    where=[]; args=[]
    if posting_id: where.append("a.job_posting_id=%s"); args.append(posting_id)
    if status: where.append("a.status=%s"); args.append(status)
    sql="""select a.id::text,a.status,a.applied_at,a.updated_at,c.id::text candidate_id,c.first_name,c.last_name,c.email,c.phone,c.source,
        p.id::text job_posting_id,p.title job_title,s.id::text stage_id,s.name stage_name
        from ugaforce_hr_applications a join ugaforce_hr_candidates c on c.id=a.candidate_id join ugaforce_hr_job_postings p on p.id=a.job_posting_id left join ugaforce_hr_pipeline_stages s on s.id=a.current_stage_id"""
    if where: sql += " where " + " and ".join(where)
    sql += " order by a.applied_at desc"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql,args); rows=[dict(r) for r in cur.fetchall()]
    return {"count":len(rows),"results":rows}


@router.post("/applications/{application_id}/stage")
def move_stage(application_id: str, payload: StageMove, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user,"HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select job_posting_id::text,current_stage_id::text,status from ugaforce_hr_applications where id=%s", (application_id,)); approw=cur.fetchone()
            if not approw: raise HTTPException(status_code=404, detail="Application not found")
            cur.execute("select id::text,name,stage_order from ugaforce_hr_pipeline_stages where id=%s and job_posting_id=%s", (payload.stage_id,approw["job_posting_id"])); stage=cur.fetchone()
            if not stage: raise HTTPException(status_code=400, detail="Stage does not belong to this job posting")
            if approw["current_stage_id"]:
                cur.execute("update ugaforce_hr_application_stage_history set exited_at=now(),outcome='advanced' where application_id=%s and stage_id=%s and exited_at is null", (application_id,approw["current_stage_id"]))
            cur.execute("insert into ugaforce_hr_application_stage_history(application_id,stage_id) values(%s,%s)", (application_id,payload.stage_id))
            cur.execute("update ugaforce_hr_applications set current_stage_id=%s,status=%s,updated_at=now() where id=%s returning id::text,status,current_stage_id::text,updated_at", (payload.stage_id,payload.application_status,application_id)); row=dict(cur.fetchone())
            emit(conn,"application.stage_advanced",{"application_id":application_id,"stage_id":payload.stage_id,"stage_name":stage["name"],"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@router.post("/offers")
def create_offer(payload: OfferCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user,"HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,status from ugaforce_hr_applications where id=%s", (payload.application_id,)); application=cur.fetchone()
            if not application: raise HTTPException(status_code=404, detail="Application not found")
            cur.execute("""insert into ugaforce_hr_offers(application_id,job_title,department_id,base_salary,bonus_target,equity_units,start_date,expires_at,created_by,status)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending_approval') returning id::text,application_id::text,job_title,base_salary,bonus_target,equity_units,start_date,status,expires_at,created_at""",
                (payload.application_id,payload.job_title,payload.department_id,payload.base_salary,payload.bonus_target,payload.equity_units,payload.start_date,payload.expires_at,user.get("employee_id")))
            row=dict(cur.fetchone())
            cur.execute("update ugaforce_hr_applications set status='offer_extended',updated_at=now() where id=%s", (payload.application_id,))
            emit(conn,"offer.created",{"offer_id":row["id"],"application_id":payload.application_id,"actor_id":user.get("employee_id")})
        conn.commit()
    return row


@router.get("/offers")
def list_offers(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user,"HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select o.id::text,o.application_id::text,o.job_title,o.base_salary,o.bonus_target,o.equity_units,o.start_date,o.status,o.expires_at,o.created_at,o.sent_at,o.responded_at,
                c.first_name,c.last_name,c.email from ugaforce_hr_offers o join ugaforce_hr_applications a on a.id=o.application_id join ugaforce_hr_candidates c on c.id=a.candidate_id order by o.created_at desc""")
            rows=[dict(r) for r in cur.fetchall()]
    return {"count":len(rows),"results":rows}


@router.post("/offers/{offer_id}/decision")
def offer_decision(offer_id: str, payload: OfferDecision, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user,"HR_SPECIALIST")
    action=payload.action.strip().lower()
    allowed={"approve","send","accept","decline","rescind"}
    if action not in allowed: raise HTTPException(status_code=400, detail=f"action must be one of {sorted(allowed)}")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,application_id::text,status,job_title,department_id::text,base_salary,start_date from ugaforce_hr_offers where id=%s", (offer_id,)); offer=cur.fetchone()
            if not offer: raise HTTPException(status_code=404, detail="Offer not found")
            transitions={"approve":("pending_approval","approved"),"send":("approved","sent"),"accept":("sent","accepted"),"decline":("sent","declined"),"rescind":(offer["status"],"rescinded")}
            expected,new_status=transitions[action]
            if action!='rescind' and offer["status"]!=expected: raise HTTPException(status_code=409, detail=f"Offer must be {expected} before {action}")
            if action=='rescind' and offer["status"] in ('accepted','declined','rescinded'): raise HTTPException(status_code=409, detail="Offer can no longer be rescinded")
            sent_expr="now()" if action=='send' else "sent_at"
            responded_expr="now()" if action in ('accept','decline') else "responded_at"
            cur.execute(f"update ugaforce_hr_offers set status=%s,sent_at={sent_expr},responded_at={responded_expr} where id=%s returning id::text,application_id::text,status,sent_at,responded_at", (new_status,offer_id)); row=dict(cur.fetchone())
            if action=='accept':
                cur.execute("update ugaforce_hr_applications set status='offer_accepted',updated_at=now() where id=%s", (offer["application_id"],))
                emit(conn,"offer.accepted",{"offer_id":offer_id,"application_id":offer["application_id"],"job_title":offer["job_title"],"department_id":offer["department_id"],"base_salary":offer["base_salary"],"start_date":offer["start_date"]})
            elif action=='decline':
                cur.execute("update ugaforce_hr_applications set status='offer_declined',updated_at=now() where id=%s", (offer["application_id"],))
                emit(conn,"offer.declined",{"offer_id":offer_id,"application_id":offer["application_id"]})
            else:
                emit(conn,f"offer.{new_status}",{"offer_id":offer_id,"application_id":offer["application_id"],"actor_id":user.get("employee_id")})
        conn.commit()
    return row

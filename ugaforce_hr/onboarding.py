from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ugaforce_hr.security import current_user, require_role

DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
router = APIRouter(prefix="/api/v1/onboarding", tags=["UGAFORCE-HR Onboarding"])


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


class TemplateTaskCreate(BaseModel):
    task_type: str
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = None
    assignee_role: str = "new_hire"
    due_offset_days: int = 0
    sort_order: int = 0
    config_json: Optional[dict[str, Any]] = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    department_id: Optional[str] = None
    role_id: Optional[str] = None
    tasks: list[TemplateTaskCreate] = Field(default_factory=list)


class StartFromOffer(BaseModel):
    employee_number: str = Field(min_length=2, max_length=40)
    work_email: Optional[str] = None
    employment_type: str = "full_time"
    template_id: Optional[str] = None


class TaskUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class DocumentCreate(BaseModel):
    employee_id: str
    title: str
    storage_key: str
    template_id: Optional[str] = None
    external_provider: Optional[str] = None
    external_envelope_id: Optional[str] = None
    expires_at: Optional[str] = None


class ProvisionCreate(BaseModel):
    employee_id: str
    system_name: str
    action: str = "provision"
    external_ref: Optional[str] = None


class EquipmentCreate(BaseModel):
    employee_id: str
    item_sku: str
    item_description: Optional[str] = None
    ship_to_address_id: Optional[str] = None


def _resolve_assignee(cur: Any, role: str, employee_id: str, manager_id: Optional[str]) -> Optional[str]:
    role = role.strip().lower()
    if role == "new_hire":
        return employee_id
    if role == "manager":
        return manager_id
    if role in {"hr_admin", "hr_specialist"}:
        cur.execute("select employee_id::text as employee_id from ugaforce_hr_users where active=true and role_name in ('HR_ADMIN','HR_MANAGER','HR_SPECIALIST') and employee_id is not null order by case role_name when 'HR_ADMIN' then 1 when 'HR_MANAGER' then 2 else 3 end limit 1")
        row = cur.fetchone()
        return row["employee_id"] if row else None
    return None


def _instantiate_tasks(cur: Any, case_id: str, template_id: Optional[str], employee_id: str, manager_id: Optional[str], hire_date: date) -> None:
    if not template_id:
        defaults = [
            ("document_sign", "Complete required employment documents", "new_hire", -3),
            ("it_provision", "Provision corporate identity and email", "hr_admin", -2),
            ("equipment_order", "Prepare assigned equipment", "hr_admin", -2),
            ("manager_task", "Manager day-one welcome and role briefing", "manager", 0),
            ("training", "Complete mandatory orientation", "new_hire", 5),
        ]
        for task_type, title, assignee_role, offset in defaults:
            assignee = _resolve_assignee(cur, assignee_role, employee_id, manager_id)
            cur.execute("insert into ugaforce_hr_onboarding_case_tasks(case_id,task_type,title,assignee_id,due_date) values(%s,%s,%s,%s,%s)", (case_id, task_type, title, assignee, hire_date + timedelta(days=offset)))
        return
    cur.execute("select id::text as id,task_type,title,assignee_role,due_offset_days from ugaforce_hr_onboarding_template_tasks where template_id=%s order by sort_order,title", (template_id,))
    for row in cur.fetchall():
        assignee = _resolve_assignee(cur, row["assignee_role"], employee_id, manager_id)
        cur.execute("insert into ugaforce_hr_onboarding_case_tasks(case_id,template_task_id,task_type,title,assignee_id,due_date) values(%s,%s,%s,%s,%s,%s)", (case_id, row["id"], row["task_type"], row["title"], assignee, hire_date + timedelta(days=row["due_offset_days"])))


@router.get("/metrics")
def metrics(user: dict[str, Any] = Depends(current_user)) -> dict[str, int]:
    require_role(user, "MANAGER")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_onboarding_cases where status in ('in_progress','overdue')")
            active = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_onboarding_case_tasks where status<>'done' and due_date<current_date")
            overdue = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_documents where status in ('sent','viewed')")
            docs = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_it_provisioning_requests where status in ('pending','in_progress')")
            provisioning = cur.fetchone()[0]
    return {"active_cases": active, "overdue_tasks": overdue, "documents_waiting": docs, "provisioning_open": provisioning}


@router.get("/templates")
def templates(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select t.id::text,t.name,t.department_id::text,d.name department_name,t.role_id::text,r.name role_name,t.is_active,t.created_at,(select count(*) from ugaforce_hr_onboarding_template_tasks x where x.template_id=t.id) task_count from ugaforce_hr_onboarding_templates t left join ugaforce_hr_departments d on d.id=t.department_id left join ugaforce_hr_roles r on r.id=t.role_id order by t.name")
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/templates")
def create_template(payload: TemplateCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    allowed_task_types = {"document_sign", "it_provision", "equipment_order", "training", "manager_task"}
    allowed_assignees = {"new_hire", "manager", "hr_admin", "hr_specialist", "it_admin"}
    for task in payload.tasks:
        if task.task_type not in allowed_task_types:
            raise HTTPException(status_code=400, detail=f"Unsupported onboarding task type: {task.task_type}")
        if task.assignee_role not in allowed_assignees:
            raise HTTPException(status_code=400, detail=f"Unsupported assignee role: {task.assignee_role}")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("insert into ugaforce_hr_onboarding_templates(name,department_id,role_id) values(%s,%s,%s) returning id::text,name,department_id::text,role_id::text,is_active,created_at", (payload.name.strip(), payload.department_id, payload.role_id))
            row = dict(cur.fetchone())
            for task in payload.tasks:
                cur.execute("insert into ugaforce_hr_onboarding_template_tasks(template_id,task_type,title,description,assignee_role,due_offset_days,sort_order,config_json) values(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)", (row["id"], task.task_type, task.title.strip(), task.description, task.assignee_role, task.due_offset_days, task.sort_order, json.dumps(task.config_json) if task.config_json is not None else None))
            emit(conn, "onboarding.template.created", {"template_id": row["id"], "actor_id": user.get("employee_id")})
        conn.commit()
    row["task_count"] = len(payload.tasks)
    return row


@router.post("/offers/{offer_id}/start")
def start_from_offer(offer_id: str, payload: StartFromOffer, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""select o.id::text,o.status,o.job_title,o.department_id::text,o.base_salary,o.start_date,o.application_id::text,
                    c.first_name,c.last_name,c.email,c.phone from ugaforce_hr_offers o
                    join ugaforce_hr_applications a on a.id=o.application_id
                    join ugaforce_hr_candidates c on c.id=a.candidate_id where o.id=%s""", (offer_id,))
                offer = cur.fetchone()
                if not offer:
                    raise HTTPException(status_code=404, detail="Offer not found")
                if offer["status"] != "accepted":
                    raise HTTPException(status_code=409, detail="Offer must be accepted before onboarding can start")
                cur.execute("select id::text,employee_id::text,status from ugaforce_hr_onboarding_cases where offer_id=%s", (offer_id,))
                existing = cur.fetchone()
                if existing:
                    return {"case_id": existing["id"], "employee_id": existing["employee_id"], "status": existing["status"], "already_started": True}
                cur.execute("select id::text as id from ugaforce_hr_roles where name='EMPLOYEE'")
                role = cur.fetchone()
                if not role:
                    raise HTTPException(status_code=503, detail="EMPLOYEE role is not initialized")
                hire_date = offer["start_date"] or date.today()
                work_email = payload.work_email or offer["email"]
                cur.execute("""insert into ugaforce_hr_employees(employee_number,first_name,last_name,personal_email,work_email,phone,hire_date,job_title,department_id,role_id,employment_type)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    returning id::text,employee_number,first_name,last_name,work_email,hire_date,job_title,department_id::text,manager_id::text,employment_status,created_at""",
                    (payload.employee_number.strip(), offer["first_name"], offer["last_name"], offer["email"], work_email, offer["phone"], hire_date, offer["job_title"], offer["department_id"], role["id"], payload.employment_type))
                employee = dict(cur.fetchone())
                cur.execute("insert into ugaforce_hr_employee_sensitive_data(employee_id,base_salary,salary_effective_at) values(%s,%s,%s) on conflict (employee_id) do update set base_salary=excluded.base_salary,salary_effective_at=excluded.salary_effective_at,updated_at=now()", (employee["id"], offer["base_salary"], hire_date))
                cur.execute("insert into ugaforce_hr_employment_history(employee_id,event_type,effective_date,new_value_json,created_by) values(%s,'hire',%s,%s::jsonb,%s)", (employee["id"], hire_date, json.dumps(employee, default=str), user.get("employee_id")))
                cur.execute("insert into ugaforce_hr_onboarding_cases(employee_id,template_id,offer_id) values(%s,%s,%s) returning id::text,status,started_at", (employee["id"], payload.template_id, offer_id))
                case = dict(cur.fetchone())
                _instantiate_tasks(cur, case["id"], payload.template_id, employee["id"], employee.get("manager_id"), hire_date)
                cur.execute("insert into ugaforce_hr_it_provisioning_requests(employee_id,system_name) values(%s,'corporate_identity'),(%s,'email'),(%s,'sso')", (employee["id"], employee["id"], employee["id"]))
                emit(conn, "employee.created_from_offer", {"employee_id": employee["id"], "offer_id": offer_id, "application_id": offer["application_id"]})
                emit(conn, "onboarding.started", {"case_id": case["id"], "employee_id": employee["id"], "offer_id": offer_id})
            conn.commit()
            return {"case_id": case["id"], "employee_id": employee["id"], "status": case["status"], "already_started": False}
        except psycopg2.errors.UniqueViolation as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Employee number or email already exists") from exc


@router.get("/cases")
def cases(status: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    args: list[Any] = []
    where = ""
    if status:
        where = " where c.status=%s"; args.append(status)
    sql = """select c.id::text,c.employee_id::text,e.employee_number,e.first_name,e.last_name,e.job_title,e.hire_date,d.name department_name,c.status,c.started_at,c.completed_at,
        count(t.id) task_count,count(t.id) filter (where t.status='done') completed_tasks,count(t.id) filter (where t.status<>'done' and t.due_date<current_date) overdue_tasks
        from ugaforce_hr_onboarding_cases c join ugaforce_hr_employees e on e.id=c.employee_id left join ugaforce_hr_departments d on d.id=e.department_id left join ugaforce_hr_onboarding_case_tasks t on t.case_id=c.id""" + where + " group by c.id,e.id,d.name order by c.started_at desc"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.get("/cases/{case_id}")
def case_detail(case_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select c.id::text,c.employee_id::text,c.status,c.started_at,c.completed_at,e.employee_number,e.first_name,e.last_name,e.job_title,e.hire_date,e.manager_id::text from ugaforce_hr_onboarding_cases c join ugaforce_hr_employees e on e.id=c.employee_id where c.id=%s", (case_id,))
            case = cur.fetchone()
            if not case:
                raise HTTPException(status_code=404, detail="Onboarding case not found")
            if user.get("role") == "EMPLOYEE" and user.get("employee_id") != case["employee_id"]:
                raise HTTPException(status_code=403, detail="Self-service access only")
            cur.execute("select id::text,task_type,title,assignee_id::text,status,due_date,completed_at,notes from ugaforce_hr_onboarding_case_tasks where case_id=%s order by due_date,title", (case_id,))
            tasks = [dict(r) for r in cur.fetchall()]
    return {"case": dict(case), "tasks": tasks}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    allowed = {"pending", "in_progress", "done", "blocked"}
    status = payload.status.strip().lower()
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select t.id::text,t.case_id::text,t.assignee_id::text,c.employee_id::text from ugaforce_hr_onboarding_case_tasks t join ugaforce_hr_onboarding_cases c on c.id=t.case_id where t.id=%s", (task_id,))
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Onboarding task not found")
            if user.get("role") == "EMPLOYEE" and user.get("employee_id") not in {task["assignee_id"], task["employee_id"]}:
                raise HTTPException(status_code=403, detail="Task is not assigned to this employee")
            completed_expr = "now()" if status == "done" else "null"
            cur.execute(f"update ugaforce_hr_onboarding_case_tasks set status=%s,notes=coalesce(%s,notes),completed_at={completed_expr} where id=%s returning id::text,case_id::text,status,due_date,completed_at,notes", (status, payload.notes, task_id))
            row = dict(cur.fetchone())
            cur.execute("select count(*) as count from ugaforce_hr_onboarding_case_tasks where case_id=%s and status<>'done'", (task["case_id"],))
            remaining = cur.fetchone()["count"]
            if remaining == 0:
                cur.execute("update ugaforce_hr_onboarding_cases set status='completed',completed_at=now() where id=%s", (task["case_id"],))
                emit(conn, "onboarding.completed", {"case_id": task["case_id"], "employee_id": task["employee_id"]})
            else:
                cur.execute("update ugaforce_hr_onboarding_cases set status=case when exists(select 1 from ugaforce_hr_onboarding_case_tasks where case_id=%s and status<>'done' and due_date<current_date) then 'overdue' else 'in_progress' end where id=%s", (task["case_id"], task["case_id"]))
            emit(conn, "onboarding.task.updated", {"task_id": task_id, "case_id": task["case_id"], "status": status, "actor_id": user.get("employee_id")})
        conn.commit()
    return row


@router.post("/documents")
def create_document(payload: DocumentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("insert into ugaforce_hr_documents(employee_id,template_id,title,storage_key,external_provider,external_envelope_id,expires_at) values(%s,%s,%s,%s,%s,%s,%s) returning id::text,employee_id::text,title,status,external_provider,expires_at,created_at", (payload.employee_id, payload.template_id, payload.title, payload.storage_key, payload.external_provider, payload.external_envelope_id, payload.expires_at))
            row = dict(cur.fetchone())
            emit(conn, "document.created", {"document_id": row["id"], "employee_id": payload.employee_id, "actor_id": user.get("employee_id")})
        conn.commit()
    return row


@router.post("/it-provisioning")
def create_provisioning(payload: ProvisionCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("insert into ugaforce_hr_it_provisioning_requests(employee_id,system_name,action,external_ref) values(%s,%s,%s,%s) returning id::text,employee_id::text,system_name,action,status,requested_at,external_ref", (payload.employee_id, payload.system_name, payload.action, payload.external_ref))
            row = dict(cur.fetchone())
            emit(conn, "it.provisioning.requested", {"request_id": row["id"], "employee_id": payload.employee_id, "system_name": payload.system_name})
        conn.commit()
    return row


@router.post("/equipment")
def create_equipment(payload: EquipmentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("insert into ugaforce_hr_equipment_orders(employee_id,item_sku,item_description,ship_to_address_id) values(%s,%s,%s,%s) returning id::text,employee_id::text,item_sku,item_description,status,ordered_at", (payload.employee_id, payload.item_sku, payload.item_description, payload.ship_to_address_id))
            row = dict(cur.fetchone())
            emit(conn, "equipment.ordered", {"equipment_order_id": row["id"], "employee_id": payload.employee_id, "item_sku": payload.item_sku})
        conn.commit()
    return row

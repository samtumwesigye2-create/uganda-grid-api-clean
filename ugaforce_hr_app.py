from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ugaforce_hr.security import authenticate, current_user, hash_password, require_role, token_hash

BASE_DIR = Path(__file__).resolve().parent
HR_DIR = BASE_DIR / "ugaforce_hr"
DASHBOARD = HR_DIR / "dashboard.html"
DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
BOOTSTRAP_KEY = os.getenv("UGAFORCE_HR_BOOTSTRAP_KEY", "")

app = FastAPI(title="UGAFORCE-HR", version="1.1.0", description="Independent corporate HR management system for the Uganda National Grid ecosystem.")
origins = [x.strip() for x in os.getenv("UGAFORCE_HR_ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False if origins == ["*"] else True, allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"], allow_headers=["Authorization","Content-Type","X-Request-ID","X-Idempotency-Key","X-HR-Bootstrap-Key"])


def db() -> Any:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def _db_status() -> dict[str, Any]:
    if not DATABASE_URL:
        return {"configured": False, "connected": False, "detail": "UGAFORCE_HR_DATABASE_URL is not set"}
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database(), current_user, version()")
                database, user, version = cur.fetchone()
                cur.execute("select to_regclass('public.ugaforce_hr_employees') is not null, to_regclass('public.ugaforce_hr_users') is not null")
                core_ready, auth_ready = cur.fetchone()
        return {"configured": True, "connected": True, "database": database, "user": user, "schema_ready": bool(core_ready and auth_ready), "engine": version.split(',')[0]}
    except Exception as exc:
        return {"configured": True, "connected": False, "detail": str(exc)[:240]}


def audit(conn: Any, actor_id: Optional[str], action: str, entity_type: str, entity_id: str, before: Any = None, after: Any = None) -> None:
    with conn.cursor() as cur:
        cur.execute("insert into ugaforce_hr_audit_log(actor_id,action,entity_type,entity_id,before_json,after_json) values(%s,%s,%s,%s,%s::jsonb,%s::jsonb)", (actor_id, action, entity_type, entity_id, json.dumps(before) if before is not None else None, json.dumps(after, default=str) if after is not None else None))
        cur.execute("insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)", (f"hr.{entity_type}.{action}", json.dumps({"entity_id": entity_id, "actor_id": actor_id, "action": action}, default=str)))


class Login(BaseModel):
    username: str
    password: str


class Bootstrap(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=200)


class EmployeeCreate(BaseModel):
    employee_number: str = Field(min_length=2, max_length=40)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    work_email: Optional[str] = None
    personal_email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: str
    job_title: Optional[str] = None
    department_id: Optional[str] = None
    manager_id: Optional[str] = None
    employment_type: str = "full_time"
    role_name: str = "EMPLOYEE"


class EmployeePatch(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    work_email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[str] = None
    manager_id: Optional[str] = None
    employment_status: Optional[str] = None
    employment_type: Optional[str] = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    parent_dept_id: Optional[str] = None


@app.get("/health")
def health() -> dict[str, Any]:
    status = _db_status()
    return {"status": "ok" if status.get("connected") else "degraded", "service": "UGAFORCE-HR", "version": app.version, "database": status}


@app.get("/api/v1/system/status")
def system_status() -> dict[str, Any]:
    return health()


@app.post("/api/v1/auth/bootstrap")
def bootstrap(payload: Bootstrap, x_hr_bootstrap_key: str = Header(default="")) -> dict[str, Any]:
    if not BOOTSTRAP_KEY or x_hr_bootstrap_key != BOOTSTRAP_KEY:
        raise HTTPException(status_code=403, detail="Bootstrap authority denied")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_users")
            if cur.fetchone()[0] > 0:
                raise HTTPException(status_code=409, detail="UGAFORCE-HR has already been initialized")
            cur.execute("insert into ugaforce_hr_users(username,password_hash,role_name) values(%s,%s,'HR_ADMIN') returning id::text", (payload.username.strip(), hash_password(payload.password)))
            uid = cur.fetchone()[0]
            audit(conn, None, "bootstrap_admin", "user", uid, after={"username": payload.username, "role": "HR_ADMIN"})
        conn.commit()
    return {"created": True, "user_id": uid, "role": "HR_ADMIN"}


@app.post("/api/v1/auth/login")
def login(payload: Login) -> dict[str, Any]:
    return authenticate(payload.username, payload.password)


@app.get("/api/v1/auth/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    safe = dict(user); safe.pop("token", None)
    return safe


@app.post("/api/v1/auth/logout")
def logout(user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("update ugaforce_hr_sessions set revoked_at=now() where token_hash=%s and revoked_at is null", (token_hash(user["token"]),))
        conn.commit()
    return {"logged_out": True}


@app.get("/api/v1/dashboard")
def dashboard_metrics(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_employees where employment_status='active'"); active = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_employees where employment_status<>'active'"); inactive = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_departments"); departments = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_profile_change_requests where status='pending'"); pending = cur.fetchone()[0]
    return {"active_employees": active, "inactive_employees": inactive, "departments": departments, "pending_approvals": pending}


@app.get("/api/v1/departments")
def departments(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,name,parent_dept_id::text,created_at from ugaforce_hr_departments order by name")
            rows = [dict(r) for r in cur.fetchall()]
    return {"results": rows}


@app.post("/api/v1/departments")
def create_department(payload: DepartmentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    try:
        with db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("insert into ugaforce_hr_departments(name,parent_dept_id) values(%s,%s) returning id::text,name,parent_dept_id::text,created_at", (payload.name.strip(), payload.parent_dept_id))
                row = dict(cur.fetchone())
                audit(conn, user.get("employee_id"), "created", "department", row["id"], after=row)
            conn.commit()
        return row
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Department already exists")


@app.get("/api/v1/employees")
def employees(q: str = Query(default=""), status: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    where, args = [], []
    if q.strip():
        where.append("(employee_number ilike %s or first_name ilike %s or last_name ilike %s or work_email ilike %s)")
        term = f"%{q.strip()}%"; args += [term,term,term,term]
    if status.strip(): where.append("employment_status=%s"); args.append(status.strip())
    sql = "select e.id::text,e.employee_number,e.first_name,e.last_name,e.work_email,e.phone,e.hire_date,e.employment_status,e.job_title,e.employment_type,e.department_id::text,d.name department_name,e.manager_id::text,e.created_at,e.updated_at from ugaforce_hr_employees e left join ugaforce_hr_departments d on d.id=e.department_id"
    if where: sql += " where " + " and ".join(where)
    sql += " order by e.last_name,e.first_name limit %s"; args.append(limit)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args); rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@app.get("/api/v1/employees/{employee_id}")
def employee(employee_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") == "EMPLOYEE" and user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Self-service access only")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select e.id::text,e.employee_number,e.first_name,e.last_name,e.personal_email,e.work_email,e.phone,e.date_of_birth,e.hire_date,e.termination_date,e.employment_status,e.job_title,e.department_id::text,d.name department_name,e.manager_id::text,e.employment_type,e.created_at,e.updated_at from ugaforce_hr_employees e left join ugaforce_hr_departments d on d.id=e.department_id where e.id=%s", (employee_id,))
            row = cur.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Employee not found")
    return dict(row)


@app.post("/api/v1/employees")
def create_employee(payload: EmployeeCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    allowed_roles = {"EMPLOYEE","MANAGER","HR_SPECIALIST","HR_MANAGER","HR_ADMIN"}
    role_name = payload.role_name.upper()
    if role_name not in allowed_roles: raise HTTPException(status_code=400, detail="Invalid role")
    if role_name in {"HR_MANAGER","HR_ADMIN"} and user.get("role") != "HR_ADMIN": raise HTTPException(status_code=403, detail="HR_ADMIN required to assign elevated HR authority")
    try:
        with db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("select id from ugaforce_hr_roles where name=%s", (role_name,)); role = cur.fetchone()
                if not role: raise HTTPException(status_code=503, detail="HR roles not initialized")
                cur.execute("""insert into ugaforce_hr_employees(employee_number,first_name,last_name,work_email,personal_email,phone,hire_date,job_title,department_id,manager_id,employment_type,role_id)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id::text,employee_number,first_name,last_name,work_email,employment_status,job_title,department_id::text,manager_id::text,employment_type,created_at""",
                    (payload.employee_number.strip(),payload.first_name.strip(),payload.last_name.strip(),payload.work_email,payload.personal_email,payload.phone,payload.hire_date,payload.job_title,payload.department_id,payload.manager_id,payload.employment_type,role["id"]))
                row = dict(cur.fetchone())
                cur.execute("insert into ugaforce_hr_employment_history(employee_id,event_type,effective_date,new_value_json,created_by) values(%s,'hire',%s,%s::jsonb,%s)", (row["id"],payload.hire_date,json.dumps(row,default=str),user.get("employee_id")))
                audit(conn, user.get("employee_id"), "created", "employee", row["id"], after=row)
            conn.commit()
        return row
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Employee number or work email already exists")


@app.patch("/api/v1/employees/{employee_id}")
def update_employee(employee_id: str, payload: EmployeePatch, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    changes = payload.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(status_code=400, detail="No changes supplied")
    allowed = {"first_name","last_name","work_email","phone","job_title","department_id","manager_id","employment_status","employment_type"}
    fields = [k for k in changes if k in allowed]
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,employee_number,first_name,last_name,work_email,phone,job_title,department_id::text,manager_id::text,employment_status,employment_type from ugaforce_hr_employees where id=%s", (employee_id,)); before = cur.fetchone()
            if not before: raise HTTPException(status_code=404, detail="Employee not found")
            sets = ",".join(f"{k}=%s" for k in fields) + ",updated_at=now()"
            cur.execute(f"update ugaforce_hr_employees set {sets} where id=%s returning id::text,employee_number,first_name,last_name,work_email,phone,job_title,department_id::text,manager_id::text,employment_status,employment_type,updated_at", [changes[k] for k in fields] + [employee_id]); after = dict(cur.fetchone())
            audit(conn, user.get("employee_id"), "updated", "employee", employee_id, before=dict(before), after=after)
        conn.commit()
    return after


@app.get("/api/v1/audit")
def audit_log(limit: int = Query(default=100, ge=1, le=500), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_MANAGER")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,actor_id::text,action,entity_type,entity_id::text,before_json,after_json,created_at from ugaforce_hr_audit_log order by created_at desc limit %s", (limit,)); rows = [dict(r) for r in cur.fetchall()]
    return {"results": rows}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD, media_type="text/html", headers={"Cache-Control": "no-store"})

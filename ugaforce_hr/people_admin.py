from __future__ import annotations

import json
import os
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ugaforce_hr.security import current_user, hash_password, require_role
from ugaforce_hr.ugacore_client import mirror_audit

router = APIRouter(prefix="/api/v1", tags=["people-admin"])
DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
ALLOWED_ROLES = {"EMPLOYEE", "MANAGER", "HR_SPECIALIST", "PAYROLL_ADMIN", "HR_MANAGER", "HR_ADMIN"}
SELF_SERVICE_FIELDS = {"personal_email", "phone"}


def db() -> Any:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def audit(conn: Any, actor_id: Optional[str], action: str, entity_type: str, entity_id: str, before: Any = None, after: Any = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "insert into ugaforce_hr_audit_log(actor_id,action,entity_type,entity_id,before_json,after_json) values(%s,%s,%s,%s,%s::jsonb,%s::jsonb)",
            (actor_id, action, entity_type, entity_id, json.dumps(before, default=str) if before is not None else None, json.dumps(after, default=str) if after is not None else None),
        )
        cur.execute(
            "insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)",
            (f"hr.{entity_type}.{action}", json.dumps({"entity_id": entity_id, "actor_id": actor_id, "action": action}, default=str)),
        )
    mirror_audit(action, entity_type, entity_id, actor_id=actor_id)


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=200)
    role_name: str = "EMPLOYEE"


class ProfileChangeCreate(BaseModel):
    field_name: str
    new_value: str = Field(max_length=500)


class ProfileDecision(BaseModel):
    action: str


@router.post("/employees/{employee_id}/account")
def provision_account(employee_id: str, payload: AccountCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    role = payload.role_name.upper().strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid HR role")
    if role in {"PAYROLL_ADMIN", "HR_MANAGER", "HR_ADMIN"} and user.get("role") != "HR_ADMIN":
        raise HTTPException(status_code=403, detail="HR_ADMIN required to grant elevated HR authority")
    try:
        with db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("select id::text,employee_number,first_name,last_name from ugaforce_hr_employees where id=%s", (employee_id,))
                employee = cur.fetchone()
                if not employee:
                    raise HTTPException(status_code=404, detail="Employee not found")
                cur.execute(
                    "insert into ugaforce_hr_users(username,password_hash,employee_id,role_name) values(%s,%s,%s,%s) returning id::text,username,employee_id::text,role_name,active,created_at",
                    (payload.username.strip(), hash_password(payload.password), employee_id, role),
                )
                account = dict(cur.fetchone())
                audit(conn, user.get("employee_id"), "account_provisioned", "employee", employee_id, after={"username": account["username"], "role": role})
            conn.commit()
        return account
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Username already exists or employee already has an account")


@router.get("/profile-change-requests")
def list_profile_changes(status: str = Query(default="pending"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """select r.id::text,r.employee_id::text,e.employee_number,e.first_name,e.last_name,r.field_name,r.old_value,r.new_value,r.status,r.requested_at,r.reviewed_by::text,r.reviewed_at
                   from ugaforce_hr_profile_change_requests r join ugaforce_hr_employees e on e.id=r.employee_id
                   where (%s='' or r.status=%s) order by r.requested_at desc limit 200""",
                (status.strip(), status.strip()),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/profile-change-requests")
def request_profile_change(payload: ProfileChangeCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=403, detail="This account is not linked to an employee profile")
    field = payload.field_name.strip()
    if field not in SELF_SERVICE_FIELDS:
        raise HTTPException(status_code=400, detail="Only personal_email and phone can be changed through self-service")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"select {field} from ugaforce_hr_employees where id=%s", (employee_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Employee not found")
            old_value = row[field]
            cur.execute(
                "insert into ugaforce_hr_profile_change_requests(employee_id,field_name,old_value,new_value) values(%s,%s,%s,%s) returning id::text,employee_id::text,field_name,old_value,new_value,status,requested_at",
                (employee_id, field, old_value, payload.new_value),
            )
            result = dict(cur.fetchone())
            audit(conn, employee_id, "profile_change_requested", "employee", employee_id, before={field: old_value}, after={field: payload.new_value})
        conn.commit()
    return result


@router.post("/profile-change-requests/{request_id}/decision")
def decide_profile_change(request_id: str, payload: ProfileDecision, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "HR_SPECIALIST")
    action = payload.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Action must be approve or reject")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,employee_id::text,field_name,old_value,new_value,status from ugaforce_hr_profile_change_requests where id=%s for update", (request_id,))
            request = cur.fetchone()
            if not request:
                raise HTTPException(status_code=404, detail="Profile change request not found")
            if request["status"] != "pending":
                raise HTTPException(status_code=409, detail="Request has already been reviewed")
            field = request["field_name"]
            if field not in SELF_SERVICE_FIELDS:
                raise HTTPException(status_code=409, detail="Request targets a field that is no longer self-service eligible")
            if action == "approve":
                cur.execute(f"update ugaforce_hr_employees set {field}=%s,updated_at=now() where id=%s", (request["new_value"], request["employee_id"]))
                status = "approved"
            else:
                status = "rejected"
            cur.execute(
                "update ugaforce_hr_profile_change_requests set status=%s,reviewed_by=%s,reviewed_at=now() where id=%s returning id::text,employee_id::text,field_name,old_value,new_value,status,reviewed_by::text,reviewed_at",
                (status, user.get("employee_id"), request_id),
            )
            result = dict(cur.fetchone())
            audit(conn, user.get("employee_id"), f"profile_change_{status}", "employee", request["employee_id"], before={field: request["old_value"]}, after={field: request["new_value"]} if status == "approved" else None)
        conn.commit()
    return result

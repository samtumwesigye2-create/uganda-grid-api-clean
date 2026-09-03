from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ugaforce_hr.security import current_user, require_role

DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
router = APIRouter(prefix="/api/v1/time", tags=["UGAFORCE-HR Time & Attendance"])


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


def _employee_scope(user: dict[str, Any], requested_employee_id: Optional[str]) -> str:
    role = user.get("role")
    own = user.get("employee_id")
    if role == "EMPLOYEE":
        if not own:
            raise HTTPException(status_code=403, detail="Employee profile is not linked")
        if requested_employee_id and requested_employee_id != own:
            raise HTTPException(status_code=403, detail="Self-service access only")
        return own
    if requested_employee_id:
        return requested_employee_id
    if own:
        return own
    raise HTTPException(status_code=400, detail="employee_id is required")


class ClockAction(BaseModel):
    action: str
    employee_id: Optional[str] = None
    source: str = "web"
    location_text: Optional[str] = None
    notes: Optional[str] = None


class LeaveRequestCreate(BaseModel):
    leave_type_id: str
    start_date: date
    end_date: date
    requested_days: Decimal = Field(gt=0)
    reason: Optional[str] = None


class LeaveDecision(BaseModel):
    action: str
    review_notes: Optional[str] = None


class TimesheetAction(BaseModel):
    action: str


@router.get("/metrics")
def metrics(user: dict[str, Any] = Depends(current_user)) -> dict[str, int]:
    require_role(user, "MANAGER")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_time_entries where clock_out is null")
            clocked_in = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_leave_requests where status='pending'")
            leave_pending = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_timesheets where status='submitted'")
            timesheets_pending = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_time_entries where clock_in::date=current_date")
            entries_today = cur.fetchone()[0]
    return {"clocked_in_now": clocked_in, "leave_pending": leave_pending, "timesheets_pending": timesheets_pending, "entries_today": entries_today}


@router.get("/attendance")
def attendance(day: date = Query(default_factory=date.today), employee_id: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") == "EMPLOYEE":
        employee_id = _employee_scope(user, employee_id or None)
    else:
        require_role(user, "MANAGER")
    where = ["te.clock_in::date=%s"]
    args: list[Any] = [day]
    if employee_id:
        where.append("te.employee_id=%s")
        args.append(employee_id)
    sql = """select te.id::text,te.employee_id::text,e.employee_number,e.first_name,e.last_name,e.job_title,
        te.clock_in,te.clock_out,te.source,te.location_text,te.notes,te.status,
        case when te.clock_out is not null then round(extract(epoch from (te.clock_out-te.clock_in))/3600.0,2) end hours
        from ugaforce_hr_time_entries te join ugaforce_hr_employees e on e.id=te.employee_id
        where """ + " and ".join(where) + " order by te.clock_in desc"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
    return {"date": day, "count": len(rows), "results": rows}


@router.post("/clock")
def clock(payload: ClockAction, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = _employee_scope(user, payload.employee_id)
    action = payload.action.strip().lower()
    if action not in {"in", "out"}:
        raise HTTPException(status_code=400, detail="action must be 'in' or 'out'")
    now = datetime.now(timezone.utc)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text from ugaforce_hr_employees where id=%s and employment_status='active'", (employee_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Active employee not found")
            if action == "in":
                try:
                    cur.execute("""insert into ugaforce_hr_time_entries(employee_id,clock_in,source,location_text,notes)
                        values(%s,%s,%s,%s,%s) returning id::text,employee_id::text,clock_in,clock_out,status""",
                        (employee_id, now, payload.source, payload.location_text, payload.notes))
                    row = dict(cur.fetchone())
                except psycopg2.errors.UniqueViolation as exc:
                    conn.rollback()
                    raise HTTPException(status_code=409, detail="Employee is already clocked in") from exc
                emit(conn, "attendance.clock_in", {"employee_id": employee_id, "time_entry_id": row["id"], "source": payload.source})
            else:
                cur.execute("""update ugaforce_hr_time_entries set clock_out=%s,status='closed',updated_at=now(),
                    notes=coalesce(%s,notes),location_text=coalesce(%s,location_text)
                    where id=(select id from ugaforce_hr_time_entries where employee_id=%s and clock_out is null order by clock_in desc limit 1)
                    returning id::text,employee_id::text,clock_in,clock_out,status""",
                    (now, payload.notes, payload.location_text, employee_id))
                found = cur.fetchone()
                if not found:
                    raise HTTPException(status_code=409, detail="Employee is not currently clocked in")
                row = dict(found)
                emit(conn, "attendance.clock_out", {"employee_id": employee_id, "time_entry_id": row["id"]})
        conn.commit()
    return row


@router.get("/leave/types")
def leave_types(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,code,name,paid,annual_entitlement_days,requires_approval from ugaforce_hr_leave_types where is_active=true order by name")
            rows = [dict(r) for r in cur.fetchall()]
    return {"results": rows}


@router.get("/leave/balances")
def leave_balances(employee_id: str = Query(default=""), year: int = Query(default_factory=lambda: date.today().year), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = _employee_scope(user, employee_id or None)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select lt.id::text leave_type_id,lt.code,lt.name,lt.paid,lt.annual_entitlement_days,
                coalesce(lb.opening_days,0) opening_days,coalesce(lb.accrued_days,lt.annual_entitlement_days) accrued_days,
                coalesce(lb.used_days,0) used_days,coalesce(lb.adjustment_days,0) adjustment_days,
                (coalesce(lb.opening_days,0)+coalesce(lb.accrued_days,lt.annual_entitlement_days)+coalesce(lb.adjustment_days,0)-coalesce(lb.used_days,0)) available_days
                from ugaforce_hr_leave_types lt left join ugaforce_hr_leave_balances lb on lb.leave_type_id=lt.id and lb.employee_id=%s and lb.year=%s
                where lt.is_active=true order by lt.name""", (employee_id, year))
            rows = [dict(r) for r in cur.fetchall()]
    return {"employee_id": employee_id, "year": year, "results": rows}


@router.get("/leave/requests")
def leave_requests(status: str = Query(default=""), employee_id: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    where: list[str] = []
    args: list[Any] = []
    if user.get("role") == "EMPLOYEE":
        where.append("lr.employee_id=%s")
        args.append(_employee_scope(user, employee_id or None))
    else:
        require_role(user, "MANAGER")
        if employee_id:
            where.append("lr.employee_id=%s")
            args.append(employee_id)
    if status:
        where.append("lr.status=%s")
        args.append(status)
    sql = """select lr.id::text,lr.employee_id::text,e.employee_number,e.first_name,e.last_name,lt.code leave_code,lt.name leave_name,
        lr.start_date,lr.end_date,lr.requested_days,lr.reason,lr.status,lr.requested_at,lr.reviewed_by::text,lr.reviewed_at,lr.review_notes
        from ugaforce_hr_leave_requests lr join ugaforce_hr_employees e on e.id=lr.employee_id join ugaforce_hr_leave_types lt on lt.id=lr.leave_type_id"""
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by lr.requested_at desc"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/leave/requests")
def create_leave_request(payload: LeaveRequestCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = _employee_scope(user, None)
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,name from ugaforce_hr_leave_types where id=%s and is_active=true", (payload.leave_type_id,))
            leave_type = cur.fetchone()
            if not leave_type:
                raise HTTPException(status_code=404, detail="Leave type not found")
            cur.execute("""select 1 from ugaforce_hr_leave_requests where employee_id=%s and status in ('pending','approved')
                and daterange(start_date,end_date,'[]') && daterange(%s,%s,'[]') limit 1""", (employee_id, payload.start_date, payload.end_date))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Leave request overlaps an existing pending or approved request")
            cur.execute("""insert into ugaforce_hr_leave_requests(employee_id,leave_type_id,start_date,end_date,requested_days,reason)
                values(%s,%s,%s,%s,%s,%s) returning id::text,employee_id::text,leave_type_id::text,start_date,end_date,requested_days,status,requested_at""",
                (employee_id, payload.leave_type_id, payload.start_date, payload.end_date, payload.requested_days, payload.reason))
            row = dict(cur.fetchone())
            emit(conn, "leave.requested", {"leave_request_id": row["id"], "employee_id": employee_id, "leave_type": leave_type["name"]})
        conn.commit()
    return row


@router.post("/leave/requests/{request_id}/decision")
def decide_leave(request_id: str, payload: LeaveDecision, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_role(user, "MANAGER")
    action = payload.action.strip().lower()
    if action not in {"approve", "reject", "cancel"}:
        raise HTTPException(status_code=400, detail="action must be approve, reject or cancel")
    new_status = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}[action]
    reviewer = user.get("employee_id")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,employee_id::text,leave_type_id::text,requested_days,status,start_date,end_date from ugaforce_hr_leave_requests where id=%s", (request_id,))
            req = cur.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="Leave request not found")
            if req["status"] != "pending" and action in {"approve", "reject"}:
                raise HTTPException(status_code=409, detail="Only pending leave requests can be reviewed")
            cur.execute("update ugaforce_hr_leave_requests set status=%s,reviewed_by=%s,reviewed_at=now(),review_notes=%s where id=%s returning id::text,status,reviewed_at", (new_status, reviewer, payload.review_notes, request_id))
            row = dict(cur.fetchone())
            if action == "approve":
                year = req["start_date"].year
                cur.execute("""insert into ugaforce_hr_leave_balances(employee_id,leave_type_id,year,used_days)
                    values(%s,%s,%s,%s) on conflict(employee_id,leave_type_id,year)
                    do update set used_days=ugaforce_hr_leave_balances.used_days+excluded.used_days""",
                    (req["employee_id"], req["leave_type_id"], year, req["requested_days"]))
            emit(conn, f"leave.{new_status}", {"leave_request_id": request_id, "employee_id": req["employee_id"], "actor_id": reviewer})
        conn.commit()
    return row


@router.get("/timesheets")
def timesheets(status: str = Query(default=""), employee_id: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    where: list[str] = []
    args: list[Any] = []
    if user.get("role") == "EMPLOYEE":
        where.append("t.employee_id=%s")
        args.append(_employee_scope(user, employee_id or None))
    else:
        require_role(user, "MANAGER")
        if employee_id:
            where.append("t.employee_id=%s")
            args.append(employee_id)
    if status:
        where.append("t.status=%s")
        args.append(status)
    sql = """select t.id::text,t.employee_id::text,e.employee_number,e.first_name,e.last_name,t.period_start,t.period_end,t.regular_hours,t.overtime_hours,t.status,t.submitted_at,t.approved_at
        from ugaforce_hr_timesheets t join ugaforce_hr_employees e on e.id=t.employee_id"""
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by t.period_start desc,e.last_name,e.first_name"
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, args)
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/timesheets/{timesheet_id}/action")
def timesheet_action(timesheet_id: str, payload: TimesheetAction, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    action = payload.action.strip().lower()
    if action not in {"submit", "approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be submit, approve or reject")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,employee_id::text,status from ugaforce_hr_timesheets where id=%s", (timesheet_id,))
            sheet = cur.fetchone()
            if not sheet:
                raise HTTPException(status_code=404, detail="Timesheet not found")
            if action == "submit":
                employee_id = _employee_scope(user, sheet["employee_id"])
                if employee_id != sheet["employee_id"]:
                    raise HTTPException(status_code=403, detail="Self-service access only")
                cur.execute("update ugaforce_hr_timesheets set status='submitted',submitted_at=now(),updated_at=now() where id=%s and status='draft' returning id::text,status,submitted_at", (timesheet_id,))
            else:
                require_role(user, "MANAGER")
                new_status = "approved" if action == "approve" else "rejected"
                cur.execute("update ugaforce_hr_timesheets set status=%s,approved_by=%s,approved_at=now(),updated_at=now() where id=%s and status='submitted' returning id::text,status,approved_at", (new_status, user.get("employee_id"), timesheet_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Timesheet cannot transition from its current state")
            row = dict(row)
            emit(conn, f"timesheet.{row['status']}", {"timesheet_id": timesheet_id, "employee_id": sheet["employee_id"], "actor_id": user.get("employee_id")})
        conn.commit()
    return row


@router.get("/holidays")
def holidays(year: int = Query(default_factory=lambda: date.today().year), country_code: str = Query(default="UG"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,holiday_date,name,country_code,region,paid from ugaforce_hr_holidays where extract(year from holiday_date)=%s and country_code=%s order by holiday_date", (year, country_code.upper()))
            rows = [dict(r) for r in cur.fetchall()]
    return {"year": year, "country_code": country_code.upper(), "results": rows}

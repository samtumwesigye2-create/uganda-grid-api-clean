from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ugaforce_hr.security import current_user
from ugaforce_hr.ugacore_client import mirror_audit

DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
router = APIRouter(prefix="/api/v1/payroll", tags=["UGAFORCE-HR Payroll & Benefits"])

PAYROLL_EDIT_ROLES = {"PAYROLL_ADMIN", "HR_ADMIN"}
PAYROLL_VIEW_ROLES = PAYROLL_EDIT_ROLES | {"HR_MANAGER"}
BENEFITS_EDIT_ROLES = PAYROLL_EDIT_ROLES | {"HR_SPECIALIST", "HR_MANAGER"}
FREQUENCY_DIVISORS = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12}


def db() -> Any:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def require_any(user: dict[str, Any], roles: set[str]) -> None:
    if user.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Payroll authority required")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def emit(conn: Any, event_type: str, payload: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "insert into ugaforce_hr_event_outbox(event_type,payload_json) values(%s,%s::jsonb)",
            (event_type, json.dumps(payload, default=str)),
        )


def audit(conn: Any, actor_id: Optional[str], action: str, entity_type: str, entity_id: str, after: Any = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "insert into ugaforce_hr_audit_log(actor_id,action,entity_type,entity_id,after_json) values(%s,%s,%s,%s,%s::jsonb)",
            (actor_id, action, entity_type, entity_id, json.dumps(after, default=str) if after is not None else None),
        )
    mirror_audit(action, entity_type, entity_id, actor_id=actor_id)


class PayGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pay_frequency: str = "biweekly"
    currency: str = Field(default="USD", min_length=3, max_length=3)
    country_code: str = Field(default="UG", min_length=2, max_length=2)


class RunCreate(BaseModel):
    period_start: str
    period_end: str
    pay_date: str
    pay_group_id: Optional[str] = None


class AdjustmentCreate(BaseModel):
    employee_id: str
    adjustment_type: str
    label: str = Field(min_length=2, max_length=180)
    amount: float


class BenefitPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category: str
    provider: Optional[str] = None
    employee_cost: float = Field(default=0, ge=0)
    employer_cost: float = Field(default=0, ge=0)


class EnrollmentCreate(BaseModel):
    employee_id: str
    plan_id: str
    tier: str = "employee_only"
    effective_date: str


@router.get("/metrics")
def metrics(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_VIEW_ROLES)
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from ugaforce_hr_payroll_runs where status in ('draft','time_locked','pending_approval')")
            open_runs = cur.fetchone()[0]
            cur.execute("select count(*) from ugaforce_hr_payroll_runs where status='pending_approval'")
            pending_approval = cur.fetchone()[0]
            cur.execute("select coalesce(sum(total_gross),0),coalesce(sum(total_net),0) from ugaforce_hr_payroll_runs where status in ('approved','disbursed') and pay_date>=date_trunc('year',current_date)")
            ytd_gross, ytd_net = cur.fetchone()
            cur.execute("select count(*) from ugaforce_hr_benefit_enrollments where status='active' and (end_date is null or end_date>=current_date)")
            active_enrollments = cur.fetchone()[0]
    return {"open_runs": open_runs, "pending_approval": pending_approval, "ytd_gross": ytd_gross, "ytd_net": ytd_net, "active_benefit_enrollments": active_enrollments}


@router.get("/pay-groups")
def pay_groups(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_VIEW_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,name,pay_frequency,currency,country_code,is_active,created_at from ugaforce_hr_pay_groups order by name")
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/pay-groups")
def create_pay_group(payload: PayGroupCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    frequency = payload.pay_frequency.strip().lower()
    if frequency not in FREQUENCY_DIVISORS:
        raise HTTPException(status_code=400, detail="Unsupported pay frequency")
    try:
        with db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("insert into ugaforce_hr_pay_groups(name,pay_frequency,currency,country_code) values(%s,%s,%s,%s) returning id::text,name,pay_frequency,currency,country_code,is_active,created_at", (payload.name.strip(), frequency, payload.currency.upper(), payload.country_code.upper()))
                row = dict(cur.fetchone())
                audit(conn, user.get("employee_id"), "created", "pay_group", row["id"], row)
                emit(conn, "payroll.pay_group.created", {"pay_group_id": row["id"]})
            conn.commit()
        return row
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Pay group already exists")


@router.get("/benefits/plans")
def benefit_plans(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select id::text,name,category,provider,employee_cost,employer_cost,is_active,created_at from ugaforce_hr_benefit_plans where is_active=true order by category,name")
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/benefits/plans")
def create_benefit_plan(payload: BenefitPlanCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, BENEFITS_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("insert into ugaforce_hr_benefit_plans(name,category,provider,employee_cost,employer_cost) values(%s,%s,%s,%s,%s) returning id::text,name,category,provider,employee_cost,employer_cost,is_active,created_at", (payload.name.strip(), payload.category.strip().lower(), payload.provider, payload.employee_cost, payload.employer_cost))
            row = dict(cur.fetchone())
            audit(conn, user.get("employee_id"), "created", "benefit_plan", row["id"], row)
            emit(conn, "benefits.plan.created", {"plan_id": row["id"]})
        conn.commit()
    return row


@router.post("/benefits/enrollments")
def create_enrollment(payload: EnrollmentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = payload.employee_id
    if user.get("role") == "EMPLOYEE":
        if user.get("employee_id") != employee_id:
            raise HTTPException(status_code=403, detail="Self-service enrollment only")
    else:
        require_any(user, BENEFITS_EDIT_ROLES)
    try:
        with db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("select 1 from ugaforce_hr_benefit_plans where id=%s and is_active=true", (payload.plan_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Active benefit plan not found")
                cur.execute("insert into ugaforce_hr_benefit_enrollments(employee_id,plan_id,tier,effective_date,status) values(%s,%s,%s,%s,'active') returning id::text,employee_id::text,plan_id::text,tier,effective_date,status,enrolled_at", (employee_id, payload.plan_id, payload.tier, payload.effective_date))
                row = dict(cur.fetchone())
                audit(conn, user.get("employee_id"), "enrolled", "benefit_enrollment", row["id"], row)
                emit(conn, "benefits.enrollment.created", {"enrollment_id": row["id"], "employee_id": employee_id})
            conn.commit()
        return row
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Employee is already enrolled for that effective date")


@router.get("/benefits/enrollments")
def enrollments(employee_id: str = Query(default=""), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") == "EMPLOYEE":
        employee_id = user.get("employee_id") or ""
    else:
        require_any(user, BENEFITS_EDIT_ROLES | PAYROLL_VIEW_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select e.id::text,e.employee_id::text,p.name plan_name,p.category,p.provider,e.tier,e.effective_date,e.end_date,e.status,p.employee_cost,p.employer_cost
                from ugaforce_hr_benefit_enrollments e join ugaforce_hr_benefit_plans p on p.id=e.plan_id
                where (%s='' or e.employee_id=%s) order by e.enrolled_at desc""", (employee_id, employee_id))
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/runs")
def create_run(payload: RunCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            pay_group_id = payload.pay_group_id
            if not pay_group_id:
                cur.execute("select id::text from ugaforce_hr_pay_groups where is_active=true order by created_at limit 1")
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=409, detail="No active pay group configured")
                pay_group_id = row["id"]
            cur.execute("insert into ugaforce_hr_payroll_runs(pay_group_id,period_start,period_end,pay_date,created_by) values(%s,%s,%s,%s,%s) returning id::text,pay_group_id::text,period_start,period_end,pay_date,status,total_gross,total_net,created_at", (pay_group_id, payload.period_start, payload.period_end, payload.pay_date, user.get("employee_id")))
            run = dict(cur.fetchone())
            audit(conn, user.get("employee_id"), "created", "payroll_run", run["id"], run)
            emit(conn, "payroll.run.created", {"payroll_run_id": run["id"]})
        conn.commit()
    return run


@router.get("/runs")
def list_runs(status: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_VIEW_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select r.id::text,r.pay_group_id::text,g.name pay_group,g.pay_frequency,g.currency,r.period_start,r.period_end,r.pay_date,r.status,r.total_gross,r.total_net,r.created_at,r.locked_at,r.approved_at,r.disbursed_at,
                (select count(*) from ugaforce_hr_payroll_line_items l where l.payroll_run_id=r.id) employee_count
                from ugaforce_hr_payroll_runs r left join ugaforce_hr_pay_groups g on g.id=r.pay_group_id
                where (%s='' or r.status=%s) order by r.pay_date desc,r.created_at desc limit %s""", (status, status, limit))
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.post("/runs/{run_id}/build")
def build_run(run_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select r.id::text,r.status,r.period_start,r.period_end,r.pay_group_id::text,g.pay_frequency from ugaforce_hr_payroll_runs r left join ugaforce_hr_pay_groups g on g.id=r.pay_group_id where r.id=%s for update", (run_id,))
            run = cur.fetchone()
            if not run:
                raise HTTPException(status_code=404, detail="Payroll run not found")
            if run["status"] != "draft":
                raise HTTPException(status_code=409, detail="Only draft payroll runs can be rebuilt")
            cur.execute("delete from ugaforce_hr_payroll_line_items where payroll_run_id=%s", (run_id,))
            divisor = Decimal(FREQUENCY_DIVISORS.get(run["pay_frequency"] or "biweekly", 26))
            cur.execute("""select e.id::text,e.employee_number,e.first_name,e.last_name,s.base_salary,
                t.id::text timesheet_id,coalesce(t.regular_hours,0) regular_hours,coalesce(t.overtime_hours,0) overtime_hours,
                coalesce((select sum(p.employee_cost) from ugaforce_hr_benefit_enrollments be join ugaforce_hr_benefit_plans p on p.id=be.plan_id where be.employee_id=e.id and be.status='active' and be.effective_date<=%s and (be.end_date is null or be.end_date>=%s)),0) benefit_cost
                from ugaforce_hr_employees e
                join ugaforce_hr_employee_sensitive_data s on s.employee_id=e.id
                left join ugaforce_hr_timesheets t on t.employee_id=e.id and t.period_start=%s and t.period_end=%s and t.status='approved'
                left join ugaforce_hr_employee_pay_groups epg on epg.employee_id=e.id
                where e.employment_status='active' and (epg.pay_group_id=%s or (epg.pay_group_id is null and %s is not null))""",
                (run["period_end"], run["period_end"], run["period_start"], run["period_end"], run["pay_group_id"], run["pay_group_id"]))
            employees = cur.fetchall()
            total_gross = Decimal("0")
            total_net = Decimal("0")
            for emp in employees:
                annual = money(emp["base_salary"])
                base_pay = money(annual / divisor)
                hourly = annual / Decimal("2080") if annual else Decimal("0")
                overtime_pay = money(hourly * Decimal("1.5") * Decimal(str(emp["overtime_hours"] or 0)))
                benefit = money(emp["benefit_cost"])
                cur.execute("select coalesce(sum(amount),0) amount from ugaforce_hr_payroll_adjustments where payroll_run_id=%s and employee_id=%s", (run_id, emp["id"]))
                adjustment = money(cur.fetchone()["amount"])
                bonus = adjustment if adjustment > 0 else Decimal("0")
                other_deductions = abs(adjustment) if adjustment < 0 else Decimal("0")
                gross = money(base_pay + overtime_pay + bonus)
                tax = Decimal("0.00")
                net = money(gross - tax - benefit - other_deductions)
                cur.execute("""insert into ugaforce_hr_payroll_line_items(payroll_run_id,employee_id,timesheet_id,base_pay,overtime_pay,bonus,gross_pay,tax_withholding,benefit_deductions,other_deductions,net_pay)
                    values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id::text""", (run_id, emp["id"], emp["timesheet_id"], base_pay, overtime_pay, bonus, gross, tax, benefit, other_deductions, net))
                line_id = cur.fetchone()["id"]
                details = [("earning","Base Pay",base_pay,10),("earning","Overtime",overtime_pay,20),("earning","Bonus / Positive Adjustments",bonus,30),("benefit_deduction","Benefits",benefit,50),("other_deduction","Other Deductions",other_deductions,60)]
                for kind,label,amount,order in details:
                    if amount:
                        cur.execute("insert into ugaforce_hr_payroll_line_item_details(line_item_id,detail_type,label,amount,sort_order) values(%s,%s,%s,%s,%s)", (line_id, kind, label, amount, order))
                total_gross += gross
                total_net += net
            cur.execute("update ugaforce_hr_payroll_runs set total_gross=%s,total_net=%s where id=%s", (money(total_gross), money(total_net), run_id))
            audit(conn, user.get("employee_id"), "built", "payroll_run", run_id, {"employees": len(employees), "total_gross": money(total_gross), "total_net": money(total_net)})
            emit(conn, "payroll.run.built", {"payroll_run_id": run_id, "employee_count": len(employees)})
        conn.commit()
    return {"payroll_run_id": run_id, "employee_count": len(employees), "total_gross": money(total_gross), "total_net": money(total_net)}


@router.post("/runs/{run_id}/adjustments")
def add_adjustment(run_id: str, payload: AdjustmentCreate, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select status from ugaforce_hr_payroll_runs where id=%s", (run_id,))
            run = cur.fetchone()
            if not run:
                raise HTTPException(status_code=404, detail="Payroll run not found")
            if run["status"] != "draft":
                raise HTTPException(status_code=409, detail="Adjustments are only allowed while the run is draft")
            cur.execute("insert into ugaforce_hr_payroll_adjustments(payroll_run_id,employee_id,adjustment_type,label,amount,created_by) values(%s,%s,%s,%s,%s,%s) returning id::text,payroll_run_id::text,employee_id::text,adjustment_type,label,amount,created_at", (run_id, payload.employee_id, payload.adjustment_type, payload.label, payload.amount, user.get("employee_id")))
            row = dict(cur.fetchone())
            audit(conn, user.get("employee_id"), "adjustment_added", "payroll_run", run_id, row)
        conn.commit()
    return row


@router.post("/runs/{run_id}/submit")
def submit_run(run_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("update ugaforce_hr_payroll_runs set status='pending_approval',locked_at=now() where id=%s and status='draft' and exists(select 1 from ugaforce_hr_payroll_line_items where payroll_run_id=%s) returning id::text,status,locked_at,total_gross,total_net", (run_id, run_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Run must be draft and built before submission")
            row = dict(row)
            audit(conn, user.get("employee_id"), "submitted", "payroll_run", run_id, row)
            emit(conn, "payroll.run.pending_approval", {"payroll_run_id": run_id})
        conn.commit()
    return row


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") not in {"HR_ADMIN", "HR_MANAGER"}:
        raise HTTPException(status_code=403, detail="HR management approval required")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("update ugaforce_hr_payroll_runs set status='approved',approved_by=%s,approved_at=now() where id=%s and status='pending_approval' returning id::text,status,total_gross,total_net,approved_at", (user.get("employee_id"), run_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Run is not pending approval")
            row = dict(row)
            audit(conn, user.get("employee_id"), "approved", "payroll_run", run_id, row)
            emit(conn, "payroll.run.approved", {"payroll_run_id": run_id})
        conn.commit()
    return row


@router.post("/runs/{run_id}/disburse")
def disburse_run(run_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_EDIT_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("update ugaforce_hr_payroll_runs set status='disbursed',disbursed_at=now() where id=%s and status='approved' returning id::text,status,total_gross,total_net,disbursed_at", (run_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Run must be approved before disbursement")
            cur.execute("update ugaforce_hr_payroll_line_items set status='paid' where payroll_run_id=%s", (run_id,))
            cur.execute("insert into ugaforce_hr_pay_slips(payroll_line_item_id,employee_id) select id,employee_id from ugaforce_hr_payroll_line_items where payroll_run_id=%s on conflict (payroll_line_item_id) do nothing", (run_id,))
            row = dict(row)
            audit(conn, user.get("employee_id"), "disbursed", "payroll_run", run_id, row)
            emit(conn, "payroll.run.disbursed", {"payroll_run_id": run_id})
        conn.commit()
    return row


@router.get("/runs/{run_id}/lines")
def run_lines(run_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_any(user, PAYROLL_VIEW_ROLES)
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select l.id::text,l.employee_id::text,e.employee_number,e.first_name,e.last_name,l.base_pay,l.overtime_pay,l.bonus,l.gross_pay,l.tax_withholding,l.benefit_deductions,l.other_deductions,l.net_pay,l.status,l.payment_reference
                from ugaforce_hr_payroll_line_items l join ugaforce_hr_employees e on e.id=l.employee_id where l.payroll_run_id=%s order by e.last_name,e.first_name""", (run_id,))
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.get("/my-payslips")
def my_payslips(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    employee_id = user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=403, detail="Account is not linked to an employee")
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select p.id::text,p.generated_at,p.viewed_at,l.gross_pay,l.net_pay,l.tax_withholding,l.benefit_deductions,r.period_start,r.period_end,r.pay_date,r.status
                from ugaforce_hr_pay_slips p join ugaforce_hr_payroll_line_items l on l.id=p.payroll_line_item_id join ugaforce_hr_payroll_runs r on r.id=l.payroll_run_id
                where p.employee_id=%s order by r.pay_date desc""", (employee_id,))
            rows = [dict(r) for r in cur.fetchall()]
    return {"count": len(rows), "results": rows}


@router.get("/payslips/{payslip_id}")
def payslip_detail(payslip_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""select p.id::text,p.employee_id::text,p.generated_at,p.viewed_at,p.storage_key,l.id::text line_item_id,l.base_pay,l.overtime_pay,l.bonus,l.gross_pay,l.tax_withholding,l.benefit_deductions,l.other_deductions,l.net_pay,
                r.period_start,r.period_end,r.pay_date,e.employee_number,e.first_name,e.last_name
                from ugaforce_hr_pay_slips p join ugaforce_hr_payroll_line_items l on l.id=p.payroll_line_item_id join ugaforce_hr_payroll_runs r on r.id=l.payroll_run_id join ugaforce_hr_employees e on e.id=p.employee_id where p.id=%s""", (payslip_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payslip not found")
            if user.get("role") == "EMPLOYEE" and user.get("employee_id") != row["employee_id"]:
                raise HTTPException(status_code=403, detail="Self-service access only")
            if user.get("role") != "EMPLOYEE":
                require_any(user, PAYROLL_VIEW_ROLES)
            cur.execute("select detail_type,label,amount,sort_order from ugaforce_hr_payroll_line_item_details where line_item_id=%s order by sort_order,id", (row["line_item_id"],))
            details = [dict(r) for r in cur.fetchall()]
            cur.execute("update ugaforce_hr_pay_slips set viewed_at=coalesce(viewed_at,now()) where id=%s", (payslip_id,))
        conn.commit()
    return {"payslip": dict(row), "details": details}

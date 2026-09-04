from __future__ import annotations
from ugaforce_hr_app import app
from ugaforce_hr.onboarding import router as onboarding_router
from ugaforce_hr.payroll import router as payroll_router
from ugaforce_hr.people_admin import router as people_admin_router
from ugaforce_hr.performance import router as performance_router
from ugaforce_hr.recruiting import public_router as careers_router, router as recruiting_router
from ugaforce_hr.time_attendance import router as time_attendance_router
from ugaforce_hr.workflow_analytics import router as workflow_analytics_router
from ugaforce_hr.ugacore_client import heartbeat
app.include_router(people_admin_router); app.include_router(recruiting_router); app.include_router(careers_router); app.include_router(onboarding_router); app.include_router(time_attendance_router); app.include_router(payroll_router); app.include_router(performance_router); app.include_router(workflow_analytics_router)
@app.on_event('startup')
def announce_startup()->None:
 heartbeat('online',version=app.version,capability='people-rbac,recruiting-ats,onboarding,time-attendance-leave,payroll-benefits,performance-management,workflow-approvals,analytics')

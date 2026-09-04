from __future__ import annotations
from ugaforce_hr_app import app
from ugaforce_hr.completion import router as completion_router
from ugaforce_hr.onboarding import router as onboarding_router
from ugaforce_hr.payroll import router as payroll_router
from ugaforce_hr.people_admin import router as people_admin_router
from ugaforce_hr.performance import router as performance_router
from ugaforce_hr.recruiting import public_router as careers_router, router as recruiting_router
from ugaforce_hr.time_attendance import router as time_attendance_router
from ugaforce_hr.workflow_analytics import router as workflow_analytics_router
from ugaforce_hr.ugacore_client import heartbeat
for r in (people_admin_router,recruiting_router,careers_router,onboarding_router,time_attendance_router,payroll_router,performance_router,workflow_analytics_router,completion_router): app.include_router(r)
@app.on_event('startup')
def announce_startup()->None:
 heartbeat('online',version=app.version,capability='people-rbac,recruiting-ats,onboarding,time-attendance-leave,payroll-benefits,performance-management,workflow-approvals,analytics,notifications,offboarding,security-readiness')

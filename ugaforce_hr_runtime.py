from __future__ import annotations

from ugaforce_hr_app import app
from ugaforce_hr.people_admin import router as people_admin_router
from ugaforce_hr.ugacore_client import heartbeat

app.include_router(people_admin_router)


@app.on_event("startup")
def announce_startup() -> None:
    # Fail-open: UGACORE may not exist yet and can never block HR startup.
    heartbeat("online", version=app.version, capability="people-rbac")

"""Production-compatible entrypoint that mounts UGATU without modifying main.py.

Run with:
    uvicorn ugatu_production_entrypoint:app --host 0.0.0.0 --port $PORT

This imports the existing National Grid FastAPI application and attaches the
UGATU command runtime as additional routers. Existing routes remain intact.
"""

import os

from fastapi.responses import Response

from main import app
from ugatu.ugatu_routes import router as ugatu_router
from ugatu.ugatu_driver_route import router as ugatu_driver_route_router
from ugatu.ugatu_driver_orders import router as ugatu_driver_orders_router
from ugatu.ugatu_driver_center import router as ugatu_driver_center_router
from ugatu.ugatu_driver_more import router as ugatu_driver_more_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _has_path(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


if not _has_path("/api/ugatu/health"):
    app.include_router(ugatu_router)
if not _has_path("/api/ugatu/driver-route/manifest"):
    app.include_router(ugatu_driver_route_router)
if not _has_path("/api/ugatu/driver-orders"):
    app.include_router(ugatu_driver_orders_router)
if not _has_path("/api/ugatu/driver-center"):
    app.include_router(ugatu_driver_center_router)
if not _has_path("/api/ugatu/driver-more"):
    app.include_router(ugatu_driver_more_router)


@app.get("/api/ugatu/integration-status", tags=["UGATU"])
def ugatu_integration_status():
    return {
        "ok": True,
        "mode": "production-compatible",
        "existing_app_preserved": True,
        "ugatu_router_mounted": True,
        "driver_route_router_mounted": True,
        "driver_orders_router_mounted": True,
        "driver_center_router_mounted": True,
        "driver_more_router_mounted": True,
        "driver_ipad_screen": "/driver/ugatu",
    }


@app.get("/driver/ugatu", tags=["UGATU"])
def ugatu_driver_ipad_screen():
    path = os.path.join(BASE_DIR, "driver-ugatu.html")
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    addons = [
        '<script src="/assets/driver-ugatu-route-v1.js"></script>',
        '<script src="/assets/driver-ugatu-orders-v1.js"></script>',
        '<script src="/assets/driver-ugatu-tasks-v1.js"></script>',
        '<script src="/assets/driver-ugatu-more-v1.js"></script>',
        '<script src="/assets/driver-ugatu-more-energy-v1.js"></script>',
    ]
    for addon in addons:
        if addon not in html:
            html = html.replace("</body>", addon + "</body>")
    return Response(content=html, media_type="text/html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

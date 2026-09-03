"""Production-compatible entrypoint that mounts UGATU without modifying main.py.

Run with:
    uvicorn ugatu_production_entrypoint:app --host 0.0.0.0 --port $PORT

This imports the existing National Grid FastAPI application and attaches the
UGATU command runtime as an additional router. Existing routes remain intact.
"""

from main import app
from ugatu.ugatu_routes import router as ugatu_router


def _already_mounted() -> bool:
    return any(getattr(route, "path", None) == "/api/ugatu/health" for route in app.routes)


if not _already_mounted():
    app.include_router(ugatu_router)


@app.get("/api/ugatu/integration-status", tags=["UGATU"])
def ugatu_integration_status():
    return {
        "ok": True,
        "mode": "production-compatible",
        "existing_app_preserved": True,
        "ugatu_router_mounted": True,
    }

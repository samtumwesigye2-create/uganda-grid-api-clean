"""Crash-resistant production bootstrap for UGAMAP/UGASHIP.

This module always exposes an ASGI app. The full application is loaded behind
an exception boundary so a startup/import failure returns diagnostics instead
of killing the Railway web process.
"""
import importlib
import logging
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response

BOOT_ERROR = None
BOOT_TRACE = None

try:
    production = importlib.import_module("ugamap_accounts_entrypoint")
    app = production.app
except BaseException as exc:  # bootstrap boundary must also catch syntax/import/system-exit failures
    BOOT_ERROR = f"{type(exc).__name__}: {exc}"
    BOOT_TRACE = traceback.format_exc()
    logging.exception("Full UGAMAP production application failed to boot")
    app = FastAPI(title="UGAMAP Emergency Runtime", docs_url=None, redoc_url=None)

    def _html_file(name: str, title: str):
        path = Path(name)
        if path.exists():
            try:
                return Response(path.read_text(encoding="utf-8"), media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
            except Exception:
                pass
        return HTMLResponse(f"<h1>{title}</h1><p>Core services are recovering. The web process is online.</p>", status_code=503)

    @app.get("/", include_in_schema=False)
    def emergency_home():
        return _html_file("index.html", "UGAMAP")

    @app.get("/ship", include_in_schema=False)
    def emergency_ship():
        return _html_file("ship.html", "UGASHIP")

    @app.get("/ship/warehouse", include_in_schema=False)
    def emergency_warehouse():
        return _html_file("warehouse.html", "UGASHIP Warehouse")

    @app.get("/admin", include_in_schema=False)
    def emergency_admin():
        return _html_file("admin.html", "UGAMAP Admin")

    @app.get("/system/startup-status", include_in_schema=False)
    def startup_status():
        return JSONResponse({"mode":"emergency","process_alive":True,"full_app_loaded":False,"error":BOOT_ERROR,"traceback":BOOT_TRACE})

if BOOT_ERROR is None:
    @app.get("/system/startup-status", include_in_schema=False)
    def startup_status_ok():
        return {"mode":"normal","process_alive":True,"full_app_loaded":True,"error":None}

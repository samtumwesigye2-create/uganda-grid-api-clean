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
from fastapi.staticfiles import StaticFiles

BOOT_ERROR = None
BOOT_TRACE = None


def _public_index_source():
    """Return the public navigation UI with embedded admin markup removed."""
    path = Path("index.html")
    if not path.exists():
        return None
    source = path.read_text(encoding="utf-8")
    start_marker = '<div id="adminOverlay" class="modal-overlay">'
    end_marker = '<div class="navWrap">'
    start = source.find(start_marker)
    end = source.find(end_marker, start if start >= 0 else 0)
    if start >= 0 and end > start:
        source = source[:start] + source[end:]
    return source


try:
    production = importlib.import_module("ugamap_accounts_entrypoint")
    app = production.app
except BaseException as exc:
    BOOT_ERROR = f"{type(exc).__name__}: {exc}"
    BOOT_TRACE = traceback.format_exc()
    logging.exception("Full UGAMAP production application failed to boot")
    app = FastAPI(title="UGAMAP Emergency Runtime", docs_url=None, redoc_url=None)

    assets = Path("assets")
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
    uploads = Path("uploads")
    if uploads.is_dir():
        app.mount("/uploads", StaticFiles(directory=str(uploads)), name="uploads")

    def _html_file(name: str, title: str):
        path = Path(name)
        if path.exists():
            try:
                source = _public_index_source() if name == "index.html" else path.read_text(encoding="utf-8")
                if source is None:
                    raise FileNotFoundError(name)
                if name == "warehouse.html":
                    source = source.replace('<header class="top"><a href="/ship">← UGASHIP</a><b>Warehouse Management</b></header>','<header class="top"><a href="/">← Uganda National Grid</a><b>Warehouse Management</b></header>',1)
                    source = source.replace('<title>UGASHIP Warehouse Management</title>','<title>Warehouse Command Dashboard</title>',1).replace('<h1>UGASHIP Warehouse Management</h1>','<h1>Warehouse Command Dashboard</h1>',1)
                return Response(source, media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
            except Exception:
                pass
        return HTMLResponse(f"<h1>{title}</h1><p>Core services are recovering. The web process is online.</p>", status_code=503)

    def _static_file(name: str, media_type: str):
        path = Path(name)
        if not path.exists():
            return Response("", status_code=404)
        return Response(path.read_text(encoding="utf-8"), media_type=media_type, headers={"Cache-Control":"no-cache, no-store, must-revalidate"})

    @app.get("/", include_in_schema=False)
    def emergency_home():
        return _html_file("index.html", "UGAMAP")

    @app.get("/app.js", include_in_schema=False)
    def emergency_app_js():
        return _static_file("app.js", "application/javascript")

    @app.get("/app-core.js", include_in_schema=False)
    def emergency_app_core_js():
        return _static_file("app-core.js", "application/javascript")

    @app.get("/boundaries.js", include_in_schema=False)
    def emergency_boundaries_js():
        return _static_file("boundaries.js", "application/javascript")

    @app.get("/legacy-grid-killer.js", include_in_schema=False)
    def emergency_legacy_grid_killer_js():
        return _static_file("legacy-grid-killer.js", "application/javascript")

    @app.get("/ship", include_in_schema=False)
    def emergency_ship():
        return _html_file("ship.html", "UGASHIP")

    @app.get("/warehouse", include_in_schema=False)
    def emergency_warehouse():
        return _html_file("warehouse.html", "Warehouse Management")

    @app.get("/admin", include_in_schema=False)
    def emergency_admin():
        return _html_file("admin.html", "UGAMAP Admin")

    @app.get("/system/startup-status", include_in_schema=False)
    def startup_status():
        return JSONResponse({"mode":"emergency","process_alive":True,"full_app_loaded":False,"error":BOOT_ERROR,"traceback":BOOT_TRACE})

if BOOT_ERROR is None:
    # Production account modules remain loaded, but the public root must stay on
    # the proven navigation UI that owns the ZIPPER/grid experience. Remove any
    # later account-specific GET / override and serve the sanitized public UI.
    for route in list(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            app.router.routes.remove(route)

    @app.get("/", include_in_schema=False)
    def proven_navigation_home():
        source = _public_index_source()
        if source is None:
            return HTMLResponse("<h1>UGAMAP</h1><p>Navigation frontend missing.</p>", status_code=503)
        return Response(source, media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})

    @app.get("/system/startup-status", include_in_schema=False)
    def startup_status_ok():
        return {"mode":"normal","process_alive":True,"full_app_loaded":True,"navigation_home":"proven-index","error":None}

    # The Platform Services page already contains the working service consoles,
    # but on phones the console sits below all nine tall service cards. Serve
    # this one static page with a tiny mobile helper injected so tapping a card
    # immediately opens/scrolls to its real workspace. No map/navigation routes
    # or backend service behavior are changed.
    _full_production_app = app

    async def app(scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") == "GET" and scope.get("path") == "/assets/platform-services.html":
            path = Path("assets/platform-services.html")
            if path.exists():
                source = path.read_text(encoding="utf-8")
                helper = '<script src="/assets/platform-services-mobile-fix.js?v=1"></script>'
                if "/assets/platform-services-mobile-fix.js" not in source:
                    source = source.replace("</body>", helper + "</body>", 1)
                response = Response(
                    source,
                    media_type="text/html",
                    headers={
                        "Cache-Control":"no-cache, no-store, must-revalidate",
                        "Strict-Transport-Security":"max-age=31536000; includeSubDomains",
                        "X-Content-Type-Options":"nosniff",
                        "X-Frame-Options":"DENY",
                        "Referrer-Policy":"strict-origin-when-cross-origin",
                        "Permissions-Policy":"camera=(self), geolocation=(self), microphone=()",
                        "Content-Security-Policy":"default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https://unpkg.com; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                    },
                )
                await response(scope, receive, send)
                return
        await _full_production_app(scope, receive, send)

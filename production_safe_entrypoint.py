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
RELEASE = "20260902-5digit-r2"
CURRENT_MAP_SCRIPTS = {
    "/app.js": "app.js",
    "/app-core.js": "app-core.js",
    "/boundaries.js": "boundaries.js",
    "/legacy-grid-killer.js": "legacy-grid-killer.js",
    "/performance-layer.js": "performance-layer.js",
}


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
    source = source.replace('/app.js?v=8', '/app.js?v=' + RELEASE)
    bridge = '<script src="/assets/zipper-search-bridge.js?v=2"></script>'
    if "/assets/zipper-search-bridge.js" not in source:
        source = source.replace("</body>", bridge + "</body>", 1) if "</body>" in source else source + bridge
    return source


def _current_script_response(path):
    filename = CURRENT_MAP_SCRIPTS.get(path)
    if not filename:
        return None
    file_path = Path(filename)
    if not file_path.exists():
        return Response("", status_code=404)
    return Response(
        file_path.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


try:
    production = importlib.import_module("ugamap_accounts_entrypoint")
    app = production.app
    from zipper_search_runtime import router as zipper_search_router
    app.include_router(zipper_search_router)
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

    @app.get("/", include_in_schema=False)
    def emergency_home():
        return _html_file("index.html", "UGAMAP")

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
        return {"mode":"normal","process_alive":True,"full_app_loaded":True,"navigation_home":"proven-index","release":RELEASE,"error":None}

    _full_production_app = app

    async def app(scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") == "GET":
            request_path = scope.get("path")
            script_response = _current_script_response(request_path)
            if script_response is not None:
                await script_response(scope, receive, send)
                return
            if request_path == "/assets/platform-services.html":
                path = Path("assets/platform-services.html")
                if path.exists():
                    source = path.read_text(encoding="utf-8")
                    helper = '<script src="/assets/platform-services-mobile-fix.js?v=1"></script>'
                    if "/assets/platform-services-mobile-fix.js" not in source:
                        source = source.replace("</body>", helper + "</body>", 1)
                    response = Response(source, media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
                    await response(scope, receive, send)
                    return
        await _full_production_app(scope, receive, send)

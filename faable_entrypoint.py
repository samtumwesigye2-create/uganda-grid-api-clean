"""Faable-specific ASGI wrapper for UGAMAP static map bootstrap files."""
from pathlib import Path
from fastapi.responses import Response
from production_safe_entrypoint import app as production_app

SCRIPT_FILES = {
    "/app-core.js": "app-core.js",
    "/boundaries.js": "boundaries.js",
    "/legacy-grid-killer.js": "legacy-grid-killer.js",
    "/performance-layer.js": "performance-layer.js",
}

async def app(scope, receive, send):
    if scope.get("type") == "http" and scope.get("method") == "GET":
        filename = SCRIPT_FILES.get(scope.get("path"))
        if filename:
            path = Path(filename)
            if path.exists():
                response = Response(
                    path.read_text(encoding="utf-8"),
                    media_type="application/javascript",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                )
                await response(scope, receive, send)
                return
    await production_app(scope, receive, send)

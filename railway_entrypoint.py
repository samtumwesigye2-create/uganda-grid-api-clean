"""Railway production wrapper: serve only the current UGAMAP frontend bundle."""
from pathlib import Path
from fastapi.responses import Response
from production_safe_entrypoint import app as production_app

RELEASE = "20260902-5digit-r3"


def _public_index():
    source = Path("index.html").read_text(encoding="utf-8")
    start_marker = '<div id="adminOverlay" class="modal-overlay">'
    end_marker = '<div class="navWrap">'
    start = source.find(start_marker)
    end = source.find(end_marker, start if start >= 0 else 0)
    if start >= 0 and end > start:
        source = source[:start] + source[end:]
    source = source.replace('/app.js?v=8', '/app.js?v=' + RELEASE)
    return source


async def app(scope, receive, send):
    if scope.get("type") == "http" and scope.get("method") == "GET":
        path = scope.get("path")
        if path == "/":
            response = Response(_public_index(), media_type="text/html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
            await response(scope, receive, send)
            return
        if path in {"/app.js", "/boundaries.js", "/performance-layer.js", "/app-core.js"}:
            filename = path.lstrip("/")
            file_path = Path(filename)
            if file_path.exists():
                response = Response(file_path.read_text(encoding="utf-8"), media_type="application/javascript", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
                await response(scope, receive, send)
                return
    await production_app(scope, receive, send)

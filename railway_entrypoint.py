"""Railway production wrapper: serve only the current UGAMAP frontend bundle."""
from pathlib import Path
import time
from fastapi.responses import Response
from production_safe_entrypoint import app as production_app
from data_relay_client import emit as relay_emit

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
    started = time.perf_counter()
    status_code = 500

    async def relay_send(message):
        nonlocal status_code
        if message.get("type") == "http.response.start":
            status_code = int(message.get("status", 500))
        await send(message)

    try:
        if scope.get("type") == "http" and scope.get("method") == "GET":
            path = scope.get("path")
            if path == "/":
                response = Response(_public_index(), media_type="text/html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
                await response(scope, receive, relay_send)
                return
            if path in {"/app.js", "/boundaries.js", "/performance-layer.js", "/app-core.js"}:
                filename = path.lstrip("/")
                file_path = Path(filename)
                if file_path.exists():
                    response = Response(file_path.read_text(encoding="utf-8"), media_type="application/javascript", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
                    await response(scope, receive, relay_send)
                    return
        await production_app(scope, receive, relay_send)
    finally:
        if scope.get("type") == "http":
            relay_emit(
                "api_call",
                "error" if status_code >= 500 else "warning" if status_code >= 400 else "info",
                {
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "service": "ugamap",
                },
            )

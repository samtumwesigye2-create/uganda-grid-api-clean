"""Railway production wrapper: serve current UGAMAP frontend and routing proxy."""
from pathlib import Path
import asyncio
import time
import requests
from fastapi.responses import Response
from production_safe_entrypoint import app as production_app
from data_relay_client import emit as relay_emit

RELEASE = "20260902-5digit-r5"
VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"


def _public_index():
    source = Path("index.html").read_text(encoding="utf-8")
    start_marker = '<div id="adminOverlay" class="modal-overlay">'
    end_marker = '<div class="navWrap">'
    start = source.find(start_marker)
    end = source.find(end_marker, start if start >= 0 else 0)
    if start >= 0 and end > start:
        source = source[:start] + source[end:]
    source = source.replace('/app.js?v=8', '/app.js?v=' + RELEASE)
    routing_fix = '<script src="/assets/routing-transport-fix.js?v=' + RELEASE + '"></script>'
    if '/assets/routing-transport-fix.js' not in source:
        source = source.replace('</body>', routing_fix + '</body>', 1) if '</body>' in source else source + routing_fix
    return source


async def _read_body(receive):
    chunks = []
    more = True
    while more:
        message = await receive()
        if message.get("type") != "http.request":
            continue
        chunks.append(message.get("body", b""))
        more = bool(message.get("more_body", False))
    return b"".join(chunks)


async def _routing_proxy(receive, send, relay_send):
    body = await _read_body(receive)
    if not body:
        response = Response('{"error":"missing route payload"}', status_code=400, media_type="application/json")
        await response({}, receive, relay_send)
        return

    def call_valhalla():
        return requests.post(
            VALHALLA_URL,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "UGAMAP/1.0"},
            timeout=15,
        )

    try:
        upstream = await asyncio.to_thread(call_valhalla)
        response = Response(
            upstream.content,
            status_code=upstream.status_code,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
    except Exception:
        response = Response(
            '{"error":"routing upstream unavailable"}',
            status_code=502,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
    await response({}, receive, relay_send)


async def app(scope, receive, send):
    started = time.perf_counter()
    status_code = 500

    async def relay_send(message):
        nonlocal status_code
        if message.get("type") == "http.response.start":
            status_code = int(message.get("status", 500))
        await send(message)

    try:
        if scope.get("type") == "http":
            method = scope.get("method")
            path = scope.get("path")

            if method == "POST" and path == "/routing/route":
                body = await _read_body(receive)

                def call_valhalla():
                    return requests.post(
                        VALHALLA_URL,
                        data=body,
                        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "UGAMAP/1.0"},
                        timeout=15,
                    )

                try:
                    upstream = await asyncio.to_thread(call_valhalla)
                    response = Response(
                        upstream.content,
                        status_code=upstream.status_code,
                        media_type="application/json",
                        headers={"Cache-Control": "no-store"},
                    )
                except Exception:
                    response = Response(
                        '{"error":"routing upstream unavailable"}',
                        status_code=502,
                        media_type="application/json",
                        headers={"Cache-Control": "no-store"},
                    )
                await response(scope, receive, relay_send)
                return

            if method == "GET":
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

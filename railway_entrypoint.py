"""Railway production wrapper: serve current UGAMAP frontend and resilient routing proxy."""
from pathlib import Path
import asyncio
import json
import time
import requests
from fastapi.responses import Response
from production_safe_entrypoint import app as production_app
from ugatu_production_entrypoint import app as ugatu_app
from data_relay_client import emit as relay_emit

RELEASE = "20260902-5digit-r8"
VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
OSRM_BASE = "https://router.project-osrm.org/route/v1/driving"


def _public_index():
    source = Path("index.html").read_text(encoding="utf-8")
    start_marker = '<div id="adminOverlay" class="modal-overlay">'
    end_marker = '<div class="navWrap">'
    start = source.find(start_marker); end = source.find(end_marker, start if start >= 0 else 0)
    if start >= 0 and end > start: source = source[:start] + source[end:]
    source = source.replace('/app.js?v=8', '/app.js?v=' + RELEASE)
    routing_fix = '<script src="/assets/routing-transport-fix.js?v=' + RELEASE + '"></script>'
    if '/assets/routing-transport-fix.js' not in source:
        source = source.replace('</body>', routing_fix + '</body>', 1) if '</body>' in source else source + routing_fix
    return source

async def _read_body(receive):
    chunks=[]
    while True:
        message=await receive()
        if message.get("type")!="http.request": continue
        chunks.append(message.get("body",b""))
        if not message.get("more_body",False): break
    return b"".join(chunks)

def _valhalla_request(body: bytes):
    return requests.post(VALHALLA_URL,data=body,headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"UGAMAP/1.0"},timeout=2.0)

def _osrm_fallback(body: bytes):
    payload=json.loads(body.decode("utf-8")); locations=payload.get("locations") or []
    if len(locations)<2: raise ValueError("route needs at least two locations")
    a,b=locations[0],locations[-1]
    coords=f"{float(a['lon'])},{float(a['lat'])};{float(b['lon'])},{float(b['lat'])}"
    r=requests.get(f"{OSRM_BASE}/{coords}",params={"overview":"full","geometries":"polyline6","steps":"false"},headers={"Accept":"application/json","User-Agent":"UGAMAP/1.0"},timeout=5.0)
    r.raise_for_status(); data=r.json(); routes=data.get("routes") or []
    if data.get("code")!="Ok" or not routes: raise ValueError(data.get("message") or data.get("code") or "OSRM route unavailable")
    route=routes[0]; geometry=route.get("geometry")
    if not geometry: raise ValueError("OSRM route geometry missing")
    converted={"trip":{"status":0,"status_message":"Found route via fallback","legs":[{"shape":geometry,"summary":{"length":float(route.get("distance",0))/1000.0,"time":float(route.get("duration",0))},"maneuvers":[]}],"summary":{"length":float(route.get("distance",0))/1000.0,"time":float(route.get("duration",0))}}}
    return json.dumps(converted).encode("utf-8")

async def _route_response(body: bytes):
    if not body: return Response('{"error":"missing route payload"}',status_code=400,media_type="application/json",headers={"Cache-Control":"no-store"})
    try:
        upstream=await asyncio.to_thread(_valhalla_request,body)
        if 200<=upstream.status_code<300:
            try:
                data=upstream.json()
                if data.get("trip") and (data.get("trip",{}).get("legs") or []):
                    return Response(upstream.content,status_code=200,media_type="application/json",headers={"Cache-Control":"no-store","X-UGAMAP-Router":"valhalla"})
            except Exception: pass
    except Exception: pass
    try:
        fallback=await asyncio.to_thread(_osrm_fallback,body)
        return Response(fallback,status_code=200,media_type="application/json",headers={"Cache-Control":"no-store","X-UGAMAP-Router":"osrm-fallback"})
    except Exception:
        return Response('{"error":"all routing engines unavailable"}',status_code=502,media_type="application/json",headers={"Cache-Control":"no-store"})

async def _routing_test():
    payload=json.dumps({"locations":[{"lat":0.3476,"lon":32.5825},{"lat":0.0512,"lon":32.4637}],"costing":"auto","units":"kilometers"}).encode("utf-8")
    started=time.perf_counter(); response=await _route_response(payload); elapsed=round((time.perf_counter()-started)*1000,2)
    ok=response.status_code==200; router=response.headers.get("X-UGAMAP-Router","none")
    return Response(json.dumps({"release":RELEASE,"routing_test":"PASS" if ok else "FAIL","router":router,"status_code":response.status_code,"elapsed_ms":elapsed,"browser_budget_ms":8000}),status_code=200 if ok else 502,media_type="application/json",headers={"Cache-Control":"no-store"})

async def app(scope,receive,send):
    started=time.perf_counter(); status_code=500
    async def relay_send(message):
        nonlocal status_code
        if message.get("type")=="http.response.start": status_code=int(message.get("status",500))
        await send(message)
    try:
        if scope.get("type")=="http":
            method=scope.get("method"); path=scope.get("path")
            if path=="/driver/ugatu" or path.startswith("/api/ugatu/"):
                await ugatu_app(scope,receive,relay_send); return
            if method=="POST" and path=="/routing/route":
                response=await _route_response(await _read_body(receive)); await response(scope,receive,relay_send); return
            if method=="GET":
                if path=="/":
                    response=Response(_public_index(),media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"}); await response(scope,receive,relay_send); return
                if path=="/system/release":
                    response=Response(json.dumps({"release":RELEASE,"routing_proxy":True,"routing_fallback":"osrm","valhalla_timeout_seconds":2,"ugatu_driver":True}),media_type="application/json",headers={"Cache-Control":"no-store"}); await response(scope,receive,relay_send); return
                if path=="/routing/test":
                    response=await _routing_test(); await response(scope,receive,relay_send); return
                if path in {"/app.js","/boundaries.js","/performance-layer.js","/app-core.js"}:
                    file_path=Path(path.lstrip("/"))
                    if file_path.exists():
                        response=Response(file_path.read_text(encoding="utf-8"),media_type="application/javascript",headers={"Cache-Control":"no-cache, no-store, must-revalidate"}); await response(scope,receive,relay_send); return
        await production_app(scope,receive,relay_send)
    finally:
        if scope.get("type")=="http": relay_emit("api_call","error" if status_code>=500 else "warning" if status_code>=400 else "info",{"method":scope.get("method"),"path":scope.get("path"),"status_code":status_code,"duration_ms":round((time.perf_counter()-started)*1000,2),"service":"ugamap"})

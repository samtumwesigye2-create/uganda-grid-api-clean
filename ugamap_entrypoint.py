"""Production entrypoint with UGAMAP Core enabled."""

from pathlib import Path
import time
import uuid

from fastapi import Form, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import Response

from entrypoint import app, national_search
from main import REPORTS, VALID_CATEGORIES, UPLOADS_DIR, addresses, prune_reports, check_admin, get_address as legacy_get_address, coordinate_lookup as legacy_coordinate_lookup
from postal_assignment import resolve_zip
from state_geometry import state_for_coordinate
from ugamap_core import configure_core, core_address, core_create_report, core_location, core_reports, core_search, router as ugamap_core_router


def _core_reports_source():
    prune_reports(); return REPORTS


def _core_report_create(category: str, lat: float, lon: float, note: str):
    category = category.strip().lower()
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    prune_reports()
    report={"id":str(uuid.uuid4()),"category":category,"lat":lat,"lon":lon,"note":str(note or "")[:200],"created_at":time.time(),"status":"new"}
    REPORTS.append(report)
    return report


def _core_search_source(query: str, limit: int):
    payload=national_search(query); results=list(payload.get("results") or [])[:limit]; return {"count":len(results),"results":results}


def _core_address_lookup(grid_id: str): return legacy_get_address(grid_id)
def _core_location_lookup(lat: float, lon: float, tolerance_m: float): return legacy_coordinate_lookup(lat=lat,lon=lon,tolerance_m=tolerance_m)


configure_core(address_source=lambda:addresses,state_lookup=state_for_coordinate,zip_lookup=resolve_zip,reports_source=_core_reports_source,report_create=_core_report_create,search_source=_core_search_source,address_lookup=_core_address_lookup,location_lookup=_core_location_lookup)
app.include_router(ugamap_core_router)

# Preserve public URLs while moving their implementation behind Core.
for route in list(app.router.routes):
    path=getattr(route,"path",None); methods=getattr(route,"methods",set())
    if path in {"/","/admin","/search","/address/{grid_id}","/coordinates/lookup","/reports","/app.js"} and "GET" in methods: app.router.routes.remove(route)
    if path=="/report" and "POST" in methods: app.router.routes.remove(route)


@app.get("/",include_in_schema=False)
def public_home_with_boundaries():
    source=Path("index.html").read_text(encoding="utf-8")
    if "/boundaries.js" not in source:
        leaflet='<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'; injected=leaflet+'\n<script src="/boundaries.js?v=3"></script>'; source=source.replace(leaflet,injected,1)
    return Response(source,media_type="text/html",headers={"Cache-Control":"no-cache"})


@app.get("/admin",include_in_schema=False)
def public_admin_with_report_notifications():
    source=Path("admin.html").read_text(encoding="utf-8")
    scripts='<script src="/admin-zip-link.js"></script>\n<script src="/assets/admin-report-notifications.js?v=3"></script>'
    source=source.replace("</body>",scripts+"</body>") if "</body>" in source else source+scripts
    return Response(source,media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})


@app.get("/search",tags=["UGAMAP Core Compatibility"])
def public_search_via_core(q:str=Query(...,min_length=1)): return core_search(q=q,limit=50)

@app.get("/address/{grid_id}",tags=["UGAMAP Core Compatibility"])
def public_address_via_core(grid_id:str): return core_address(grid_id)

@app.get("/coordinates/lookup",tags=["UGAMAP Core Compatibility"])
def public_coordinate_lookup_via_core(lat:float=Query(...),lon:float=Query(...),tolerance_m:float=Query(default=15.0,ge=0.0,le=500.0)): return core_location(lat=lat,lon=lon,tolerance_m=tolerance_m)

@app.get("/reports",tags=["UGAMAP Core Compatibility"])
def public_reports_via_core():
    payload=core_reports(); active=[r for r in payload.get("results",[]) if str(r.get("status","new")).lower()!="resolved"]
    return {"count":len(active),"results":active}

@app.post("/report",tags=["UGAMAP Core Compatibility"])
async def public_report_via_core(category:str=Form(...),lat:float=Form(...),lon:float=Form(...),note:str=Form(""),file:UploadFile=File(None)):
    media_url=None; media_type=None
    if file and file.filename:
        media_type=(file.content_type or "").lower()
        if not (media_type.startswith("image/") or media_type.startswith("video/")):
            raise HTTPException(status_code=400,detail="Report attachment must be an image or video")
        data=await file.read()
        if len(data)>15*1024*1024:
            raise HTTPException(status_code=413,detail="Report attachment is too large (max 15MB)")
        suffix=Path(file.filename).suffix.lower(); allowed={".jpg",".jpeg",".png",".gif",".webp",".heic",".heif",".mp4",".mov",".webm",".m4v"}
        if suffix not in allowed: suffix=".jpg" if media_type.startswith("image/") else ".mp4"
        filename="report-"+uuid.uuid4().hex+suffix; Path(UPLOADS_DIR,filename).write_bytes(data); media_url="/uploads/"+filename
    report=core_create_report(category=category,lat=lat,lon=lon,note=note)
    if media_url:
        report["media_url"]=media_url; report["media_type"]=media_type
        for saved in REPORTS:
            if saved.get("id")==report.get("id"):
                saved["media_url"]=media_url; saved["media_type"]=media_type; break
    return report


@app.post("/admin/reports/{report_id}/status",tags=["UGAMAP Admin Reports"])
def admin_report_status(report_id:str,status:str=Form(...),x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode); value=status.strip().lower()
    if value not in {"new","reviewed","resolved"}: raise HTTPException(status_code=400,detail="Status must be new, reviewed, or resolved")
    prune_reports()
    for report in REPORTS:
        if report.get("id")==report_id:
            report["status"]=value; report["status_updated_at"]=time.time(); return report
    raise HTTPException(status_code=404,detail="Report not found")


@app.get("/app.js",include_in_schema=False)
def public_app_js_via_core():
    source=Path("app.js").read_text(encoding="utf-8")
    old_start="  async function fetchValhalla(payload, attempt = 1) {"; old_end="  function decodeShape(str) {"; start=source.find(old_start); end=source.find(old_end,start)
    if start<0 or end<0:return Response(source,media_type="application/javascript")
    replacement=r'''  async function getRoute(a, b) {
    const params = new URLSearchParams({start_lat:String(a.lat),start_lon:String(a.lon),dest_lat:String(b.lat),dest_lon:String(b.lon),mode:mode.value});
    let lastError=null;
    for(const base of apiCandidates()){
      try{const controller=new AbortController();const timeoutId=setTimeout(()=>controller.abort(),12000);const r=await fetch(base+'/core/route?'+params.toString(),{signal:controller.signal});clearTimeout(timeoutId);const d=await r.json();if(!r.ok)throw new Error((d&&d.detail)||('HTTP '+r.status));const pts=Array.isArray(d.points)?d.points:[];if(pts.length<2)throw new Error('No route found');const cumDist=computeCumDist(pts);const maneuvers=parseManeuvers(d.maneuvers||[],pts,cumDist);return{pts,distance:Number(d.distance_m||0),duration:Number(d.duration_s||0),maneuvers,cumDist};}catch(e){lastError=e;}}
    throw lastError||new Error('UGAMAP routing service unavailable');
  }

'''
    patched=source[:start]+replacement+source[end:]
    return Response(patched,media_type="application/javascript",headers={"Cache-Control":"no-cache"})

from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json, os, time, uuid
from postal_assignment import resolve_zip
from grid_assignment import next_grid_id
from state_geometry import state_feature_collection
from national_zip_geometry import zip_feature_collection, validation_status
from manual_zip_assignments import list_assignments, available_reserves, create_assignment, delete_assignment, feature_collection as manual_zip_features

app=FastAPI(title="Uganda National Grid API",version="1.6")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DATABASE=os.path.join(BASE_DIR,"entebbe_database.json")
INDEX_FILE=os.path.join(BASE_DIR,"index.html");APP_JS_FILE=os.path.join(BASE_DIR,"app.js");BOUNDARIES_JS_FILE=os.path.join(BASE_DIR,"boundaries.js")
SUBMIT_FILE=os.path.join(BASE_DIR,"submit.html");REVIEW_FILE=os.path.join(BASE_DIR,"review.html");ADMIN_FILE=os.path.join(BASE_DIR,"admin.html");SHIP_FILE=os.path.join(BASE_DIR,"ship.html");DRIVER_FILE=os.path.join(BASE_DIR,"driver.html");TEST_TOOL_FILE=os.path.join(BASE_DIR,"test-tool.html")
ASSETS_DIR=os.path.join(BASE_DIR,"assets")
if os.path.isdir(ASSETS_DIR):app.mount("/assets",StaticFiles(directory=ASSETS_DIR),name="assets")
UPLOADS_DIR=os.path.join(BASE_DIR,"uploads");os.makedirs(UPLOADS_DIR,exist_ok=True);app.mount("/uploads",StaticFiles(directory=UPLOADS_DIR),name="uploads")
BUSINESS_DOCS_DIR=os.path.join(BASE_DIR,"business-documents")
if os.path.isdir(BUSINESS_DOCS_DIR):app.mount("/business-documents",StaticFiles(directory=BUSINESS_DOCS_DIR,html=True),name="business-documents")
ADMIN_PASSCODE=os.environ.get("ADMIN_PASSCODE","uganda2026")
try:
    with open(DATABASE,"r",encoding="utf-8") as f:addresses=json.load(f)
except Exception:addresses=[]
def save_addresses(v):
    global addresses;addresses=v
    try:
        with open(DATABASE,"w",encoding="utf-8") as f:json.dump(addresses,f,ensure_ascii=False,indent=2)
    except Exception:pass
REPORTS=[];REPORT_TTL_SECONDS=21600;VALID_CATEGORIES={"police","accident","road_closure","bridge","traffic","weather"};SUBMISSIONS=[];VALID_BUILDING_TYPES={"hospital","police","government","residence","business","other"};ALLOWED_MEDIA_TYPES={"image/jpeg","image/png","image/webp","image/gif","video/mp4","video/quicktime","video/webm"};MAX_MEDIA_BYTES=15*1024*1024
from shipments import router as shipments_router,register_rate_routes
register_rate_routes(lambda:addresses);app.include_router(shipments_router)
from commercial import router as commercial_router,register_commercial_routes
register_commercial_routes(lambda:addresses,save_addresses);app.include_router(commercial_router)
from auth import router as auth_router;app.include_router(auth_router)
from inventory import router as inventory_router;app.include_router(inventory_router)
from invoicing import router as invoicing_router;app.include_router(invoicing_router)
from mailing import router as mailing_router;app.include_router(mailing_router)
from data_hub import router as data_router;app.include_router(data_router)
from users import router as users_router;app.include_router(users_router)
from drivers import router as drivers_router;app.include_router(drivers_router)
from customer_tools import router as customer_tools_router;app.include_router(customer_tools_router)
def check_admin(v):
    if v!=ADMIN_PASSCODE:raise HTTPException(status_code=401,detail="Invalid passcode")
def prune_reports():
    global REPORTS;now=time.time();REPORTS=[r for r in REPORTS if now-r["created_at"]<REPORT_TTL_SECONDS]
@app.get("/health")
def health():return {"status":"ok","records":len(addresses)}
@app.get("/geography/states")
def geography_states():return state_feature_collection()
@app.get("/geography/zips")
def geography_zips():
    base=zip_feature_collection();base["features"].extend(manual_zip_features()["features"]);return base
@app.get("/geography/status")
def geography_status():return validation_status()
@app.get("/admin/zips/manual")
def admin_manual_zips(x_admin_passcode:str=Header(default="")):check_admin(x_admin_passcode);return {"results":list_assignments()}
@app.get("/admin/zips/reserves/{region}")
def admin_zip_reserves(region:str,x_admin_passcode:str=Header(default="")):check_admin(x_admin_passcode);return {"region":region.upper(),"results":available_reserves(region.upper())}
@app.post("/admin/zips/manual")
def admin_create_zip(payload:dict,x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode)
    try:return create_assignment(str(payload.get("zip_code","")),str(payload.get("postal_region","")).upper(),str(payload.get("state_code","")),str(payload.get("name","")),payload.get("geometry"))
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e))
@app.delete("/admin/zips/manual/{zip_code}")
def admin_delete_zip(zip_code:str,x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode)
    if not delete_assignment(zip_code):raise HTTPException(status_code=404,detail="Manual ZIP assignment not found")
    return {"deleted":True,"zip_code":zip_code}
@app.api_route("/",methods=["GET","HEAD"])
def home():return FileResponse(INDEX_FILE,media_type="text/html")
@app.get("/app.js")
def app_js():
    with open(APP_JS_FILE,"r",encoding="utf-8") as f:code=f.read()
    if os.path.exists(BOUNDARIES_JS_FILE):
        with open(BOUNDARIES_JS_FILE,"r",encoding="utf-8") as f:code=f.read()+"\n\n"+code
    return Response(content=code,media_type="application/javascript",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
@app.get("/boundaries.js")
def boundaries_js():return FileResponse(BOUNDARIES_JS_FILE,media_type="application/javascript; charset=utf-8",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
@app.get("/submit")
def submit_page():return FileResponse(SUBMIT_FILE,media_type="text/html")
@app.get("/review")
def review_page():return FileResponse(REVIEW_FILE,media_type="text/html")
@app.get("/admin")
def admin_page():return FileResponse(ADMIN_FILE,media_type="text/html")
@app.get("/ship")
def ship_page():return FileResponse(SHIP_FILE,media_type="text/html")
@app.get("/driver")
def driver_page():return FileResponse(DRIVER_FILE,media_type="text/html")
@app.get("/test-tool")
def test_tool_page():return FileResponse(TEST_TOOL_FILE,media_type="text/html")
@app.get("/search")
def search(q:str=Query(...,min_length=1)):
    x=q.strip().lower();r=[a for a in addresses if x in str(a.get("grid_id","")).lower() or x in str(a.get("address","")).lower()][:50];return {"count":len(r),"results":r}
@app.get("/address/{grid_id}")
def get_address(grid_id:str):
    for a in addresses:
        if str(a.get("grid_id","")).strip().lower()==grid_id.strip().lower():return a
    raise HTTPException(status_code=404,detail="Address not found")
@app.put("/address/{grid_id}")
def update_address(grid_id:str,address:str=Form(None),latitude:float=Form(None),longitude:float=Form(None),address_type:str=Form(None),x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode);found=None
    for a in addresses:
        if str(a.get("grid_id","")).strip().lower()==grid_id.strip().lower():
            if address is not None:a["address"]=address
            if latitude is not None:a["latitude"]=latitude
            if longitude is not None:a["longitude"]=longitude
            if address_type is not None:a["address_type"]=address_type
            found=a
    if not found:raise HTTPException(status_code=404,detail="Address not found")
    save_addresses(addresses);return found
@app.delete("/address/{grid_id}")
def delete_address(grid_id:str,x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode);new=[a for a in addresses if str(a.get("grid_id","")).strip().lower()!=grid_id.strip().lower()]
    if len(new)==len(addresses):raise HTTPException(status_code=404,detail="Address not found")
    save_addresses(new);return {"grid_id":grid_id,"deleted":True}
@app.get("/stats")
def stats():return {"total_records":len(addresses),"residential_records":sum(1 for a in addresses if a.get("address_type","residential")=="residential"),"commercial_records":sum(1 for a in addresses if a.get("address_type")=="commercial")}
@app.post("/report")
async def create_report(category:str=Form(...),lat:float=Form(...),lon:float=Form(...),note:str=Form(""),file:UploadFile=File(None)):
    category=category.strip().lower()
    if category not in VALID_CATEGORIES:raise HTTPException(status_code=400,detail="Invalid category")
    prune_reports();report={"id":str(uuid.uuid4()),"category":category,"lat":lat,"lon":lon,"note":note[:200],"created_at":time.time()};REPORTS.append(report);return report
@app.get("/reports")
def list_reports():prune_reports();return {"count":len(REPORTS),"results":REPORTS}
@app.post("/submissions")
async def create_submission(lat:float=Form(...),lon:float=Form(...),building_type:str=Form(...),note:str=Form(""),file:UploadFile=File(None)):
    if building_type.strip().lower() not in VALID_BUILDING_TYPES:raise HTTPException(status_code=400,detail="Invalid building type")
    s={"id":str(uuid.uuid4()),"lat":lat,"lon":lon,"building_type":building_type,"note":note[:300],"status":"pending","created_at":time.time()};SUBMISSIONS.append(s);return s
@app.get("/submissions")
def list_submissions(status:str=Query(default=""),x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode);items=SUBMISSIONS if not status else [s for s in SUBMISSIONS if s["status"]==status];return {"count":len(items),"results":list(reversed(items))}
@app.post("/submissions/{submission_id}/decision")
def decide_submission(submission_id:str,action:str=Form(...),grid_id:str=Form(""),address:str=Form(""),x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode);sub=next((s for s in SUBMISSIONS if s["id"]==submission_id),None)
    if not sub:raise HTTPException(status_code=404,detail="Submission not found")
    if action.strip().lower()=="deny":sub["status"]="denied";return sub
    assignment=next_grid_id(sub["lat"],sub["lon"],addresses);postal=resolve_zip(sub["lat"],sub["lon"]);sub.update({"status":"approved","assigned_grid_id":assignment["grid_id"],"assigned_address":address})
    rec={"grid_id":assignment["grid_id"],"address":address,"latitude":sub["lat"],"longitude":sub["lon"],"state_code":assignment["state_code"],"state_name":assignment["state_name"],"postal_prefix":assignment["postal_prefix"]}
    if postal:rec.update({"zip_code":postal["zip_code"],"postal_region":postal["region"]});sub["assigned_zip_code"]=postal["zip_code"]
    save_addresses(addresses+[rec]);return sub

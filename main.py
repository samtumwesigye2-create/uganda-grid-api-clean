from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os
import time
import uuid
import urllib.request
import xml.etree.ElementTree as ET
from postal_assignment import resolve_zip
from grid_assignment import next_grid_id
from state_geometry import state_feature_collection
from national_zip_geometry import zip_feature_collection, validation_status

app = FastAPI(title="Uganda National Grid API", version="1.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "entebbe_database.json")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
APP_JS_FILE = os.path.join(BASE_DIR, "app.js")
SUBMIT_FILE = os.path.join(BASE_DIR, "submit.html")
REVIEW_FILE = os.path.join(BASE_DIR, "review.html")
ADMIN_FILE = os.path.join(BASE_DIR, "admin.html")
SHIP_FILE = os.path.join(BASE_DIR, "ship.html")
DRIVER_FILE = os.path.join(BASE_DIR, "driver.html")
TEST_TOOL_FILE = os.path.join(BASE_DIR, "test-tool.html")

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

BUSINESS_DOCS_DIR = os.path.join(BASE_DIR, "business-documents")
if os.path.isdir(BUSINESS_DOCS_DIR):
    app.mount("/business-documents", StaticFiles(directory=BUSINESS_DOCS_DIR, html=True), name="business-documents")

ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)
except Exception:
    addresses = []


def save_addresses(updated_addresses):
    global addresses
    addresses = updated_addresses
    try:
        with open(DATABASE, "w", encoding="utf-8") as file:
            json.dump(addresses, file, ensure_ascii=False, indent=2)
    except Exception:
        pass

REPORTS = []
REPORT_TTL_SECONDS = 6 * 3600
VALID_CATEGORIES = {"police", "accident", "road_closure", "bridge", "traffic", "weather"}
SUBMISSIONS = []
VALID_BUILDING_TYPES = {"hospital", "police", "government", "residence", "business", "other"}
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime", "video/webm"}
MAX_MEDIA_BYTES = 15 * 1024 * 1024

from shipments import router as shipments_router, register_rate_routes
register_rate_routes(lambda: addresses)
app.include_router(shipments_router)
from commercial import router as commercial_router, register_commercial_routes
register_commercial_routes(lambda: addresses, save_addresses)
app.include_router(commercial_router)
from auth import router as auth_router
app.include_router(auth_router)
from inventory import router as inventory_router
app.include_router(inventory_router)
from invoicing import router as invoicing_router
app.include_router(invoicing_router)
from mailing import router as mailing_router
app.include_router(mailing_router)
from data_hub import router as data_router
app.include_router(data_router)
from users import router as users_router
app.include_router(users_router)
from drivers import router as drivers_router
app.include_router(drivers_router)
from customer_tools import router as customer_tools_router
app.include_router(customer_tools_router)

def prune_reports():
    now = time.time()
    global REPORTS
    REPORTS = [r for r in REPORTS if now - r["created_at"] < REPORT_TTL_SECONDS]

def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")

@app.get("/health")
def health():
    return {"status": "ok", "records": len(addresses)}

@app.get("/geography/states")
def geography_states():
    return state_feature_collection()

@app.get("/geography/zips")
def geography_zips():
    return zip_feature_collection()

@app.get("/geography/status")
def geography_status():
    return validation_status()

@app.api_route("/", methods=["GET", "HEAD"])
def home():
    if not os.path.exists(INDEX_FILE): raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_FILE, media_type="text/html")

@app.get("/app.js")
def app_js():
    if not os.path.exists(APP_JS_FILE): raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(APP_JS_FILE, media_type="application/javascript; charset=utf-8", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/submit")
def submit_page(): return FileResponse(SUBMIT_FILE, media_type="text/html")
@app.get("/review")
def review_page(): return FileResponse(REVIEW_FILE, media_type="text/html")
@app.get("/admin")
def admin_page(): return FileResponse(ADMIN_FILE, media_type="text/html")
@app.get("/ship")
def ship_page(): return FileResponse(SHIP_FILE, media_type="text/html")
@app.get("/driver")
def driver_page(): return FileResponse(DRIVER_FILE, media_type="text/html")
@app.get("/test-tool")
def test_tool_page(): return FileResponse(TEST_TOOL_FILE, media_type="text/html")

@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    query=q.strip().lower(); results=[]
    for item in addresses:
        if query in str(item.get("grid_id","")).lower() or query in str(item.get("address","")).lower(): results.append(item)
        if len(results)>=50: break
    return {"count":len(results),"results":results}

@app.get("/address/{grid_id}")
def get_address(grid_id: str):
    for item in addresses:
        if str(item.get("grid_id","")).strip().lower()==grid_id.strip().lower(): return item
    raise HTTPException(status_code=404, detail="Address not found")

@app.put("/address/{grid_id}")
def update_address(grid_id: str, address: str = Form(None), latitude: float = Form(None), longitude: float = Form(None), address_type: str = Form(None), x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode); found=None; updated=[]
    for item in addresses:
        if str(item.get("grid_id","")).strip().lower()==grid_id.strip().lower():
            if address is not None: item["address"]=address
            if latitude is not None: item["latitude"]=latitude
            if longitude is not None: item["longitude"]=longitude
            if address_type is not None: item["address_type"]=address_type
            found=item
        updated.append(item)
    if not found: raise HTTPException(status_code=404, detail="Address not found")
    save_addresses(updated); return found

@app.delete("/address/{grid_id}")
def delete_address(grid_id: str, x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    updated=[a for a in addresses if str(a.get("grid_id","")).strip().lower()!=grid_id.strip().lower()]
    if len(updated)==len(addresses): raise HTTPException(status_code=404, detail="Address not found")
    save_addresses(updated); return {"grid_id":grid_id,"deleted":True}

@app.get("/stats")
def stats():
    residential=sum(1 for a in addresses if a.get("address_type","residential")=="residential")
    commercial=sum(1 for a in addresses if a.get("address_type")=="commercial")
    return {"total_records":len(addresses),"residential_records":residential,"commercial_records":commercial,"database":"entebbe_database.json","frontend":"index.html + app.js"}

@app.post("/report")
async def create_report(category: str = Form(...), lat: float = Form(...), lon: float = Form(...), note: str = Form(""), file: UploadFile = File(None)):
    category=category.strip().lower()
    if category not in VALID_CATEGORIES: raise HTTPException(status_code=400,detail="Invalid category")
    prune_reports(); media_url=""; media_type=""
    if file is not None and file.filename:
        contents=await file.read()
        if file.content_type not in ALLOWED_MEDIA_TYPES: raise HTTPException(status_code=400,detail="Unsupported file type")
        if len(contents)>MAX_MEDIA_BYTES: raise HTTPException(status_code=400,detail="File too large (max 15MB)")
        filename=str(uuid.uuid4())+os.path.splitext(file.filename)[1][:10]
        with open(os.path.join(UPLOADS_DIR,filename),"wb") as out: out.write(contents)
        media_url="/uploads/"+filename; media_type=file.content_type
    report={"id":str(uuid.uuid4()),"category":category,"lat":lat,"lon":lon,"note":note.strip()[:200],"media_url":media_url,"media_type":media_type,"created_at":time.time()}
    REPORTS.append(report); return report

@app.get("/reports")
def list_reports(): prune_reports(); return {"count":len(REPORTS),"results":REPORTS}

@app.post("/submissions")
async def create_submission(lat: float = Form(...), lon: float = Form(...), building_type: str = Form(...), note: str = Form(""), file: UploadFile = File(None)):
    building_type=building_type.strip().lower()
    if building_type not in VALID_BUILDING_TYPES: raise HTTPException(status_code=400,detail="Invalid building type")
    media_url=""; media_type=""
    if file is not None and file.filename:
        contents=await file.read()
        if file.content_type not in ALLOWED_MEDIA_TYPES: raise HTTPException(status_code=400,detail="Unsupported file type")
        if len(contents)>MAX_MEDIA_BYTES: raise HTTPException(status_code=400,detail="File too large (max 15MB)")
        filename=str(uuid.uuid4())+os.path.splitext(file.filename)[1][:10]
        with open(os.path.join(UPLOADS_DIR,filename),"wb") as out: out.write(contents)
        media_url="/uploads/"+filename; media_type=file.content_type
    submission={"id":str(uuid.uuid4()),"lat":lat,"lon":lon,"building_type":building_type,"note":note.strip()[:300],"media_url":media_url,"media_type":media_type,"status":"pending","assigned_grid_id":"","assigned_address":"","created_at":time.time()}
    SUBMISSIONS.append(submission); return submission

@app.get("/submissions")
def list_submissions(status: str = Query(default=""), x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode); items=SUBMISSIONS
    if status: items=[s for s in items if s["status"]==status]
    return {"count":len(items),"results":list(reversed(items))}

@app.post("/submissions/{submission_id}/decision")
def decide_submission(submission_id: str, action: str = Form(...), grid_id: str = Form(""), address: str = Form(""), x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode); action=action.strip().lower()
    if action not in {"approve","deny"}: raise HTTPException(status_code=400,detail="Invalid action")
    sub=next((s for s in SUBMISSIONS if s["id"]==submission_id),None)
    if not sub: raise HTTPException(status_code=404,detail="Submission not found")
    if action=="deny": sub["status"]="denied"; return sub
    address=address.strip()
    if not address: raise HTTPException(status_code=400,detail="address is required to approve")
    assignment=next_grid_id(sub["lat"],sub["lon"],addresses)
    grid_id=assignment["grid_id"]
    sub["status"]="approved"; sub["assigned_grid_id"]=grid_id; sub["assigned_address"]=address
    sub["assigned_state_code"]=assignment["state_code"]; sub["assigned_state_name"]=assignment["state_name"]
    postal=resolve_zip(sub["lat"],sub["lon"])
    new_record={"grid_id":grid_id,"address":address,"latitude":sub["lat"],"longitude":sub["lon"],"address_type":"residential","state_code":assignment["state_code"],"state_name":assignment["state_name"],"postal_prefix":assignment["postal_prefix"]}
    if postal:
        new_record["zip_code"]=postal["zip_code"]; new_record["postal_region"]=postal["region"]; new_record["postal_zone"]=postal.get("name",""); sub["assigned_zip_code"]=postal["zip_code"]
    save_addresses(addresses+[new_record]); return sub

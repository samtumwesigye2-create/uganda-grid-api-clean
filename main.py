from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import json, os, time, uuid, math
from postal_assignment import resolve_zip
from grid_assignment import next_grid_id
from state_geometry import state_feature_collection, state_for_coordinate
from national_zip_geometry import zip_feature_collection, validation_status
from manual_zip_assignments import list_assignments, available_reserves, create_assignment, delete_assignment, feature_collection as manual_zip_features
from special_zip_assignments import list_assignments as list_special_zips, create_assignment as create_special_zip, delete_assignment as delete_special_zip, category_catalog as special_zip_catalog, feature_collection as special_zip_features
from address_confidence import evaluate_address_application
from submission_store import create_submission as store_create_submission, list_submissions as store_list_submissions, get_submission as store_get_submission, update_submission as store_update_submission

app=FastAPI(title="Uganda National Grid API",version="2.0")
ALLOWED_ORIGINS=[x.strip() for x in os.environ.get("ALLOWED_ORIGINS","https://uganda-grid-api-clean-production.up.railway.app").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Access-Code","X-Admin-Passcode","X-Driver-Passcode","X-MFA-Token","X-Idempotency-Key","X-UGA-Signature","X-UGA-Idempotency-Key","X-UGA-Event-Type"])
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
def F(n):return os.path.join(BASE_DIR,n)
DATABASE=F("entebbe_database.json");INDEX_FILE=F("index.html");APP_JS_FILE=F("app.js");BOUNDARIES_JS_FILE=F("boundaries.js");SUBMIT_FILE=F("submit.html");REVIEW_FILE=F("review.html");ADMIN_FILE=F("admin.html");ADMIN_ZIP_LINK_FILE=F("admin-zip-link.js");ZIP_ADMIN_FILE=F("zip-admin.html");SPECIAL_ZIP_ADMIN_FILE=F("special-zip-admin.html");SHIP_FILE=F("ship.html");DRIVER_FILE=F("driver.html");TEST_TOOL_FILE=F("test-tool.html")
ASSETS_DIR=F("assets")
if os.path.isdir(ASSETS_DIR):app.mount("/assets",StaticFiles(directory=ASSETS_DIR),name="assets")
UPLOADS_DIR=F("uploads");os.makedirs(UPLOADS_DIR,exist_ok=True);app.mount("/uploads",StaticFiles(directory=UPLOADS_DIR),name="uploads")
BUSINESS_DOCS_DIR=F("business-documents")
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
REPORTS=[];REPORT_TTL_SECONDS=21600;VALID_CATEGORIES={"police","accident","road_closure","bridge","traffic","weather"};VALID_BUILDING_TYPES={"hospital","police","government","residence","business","other"}
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
def special_zip_search_records():
 return [{"grid_id":x.get("zip_code", ""),"zip_code":x.get("zip_code", ""),"address":x.get("name", ""),"display_name":x.get("name", ""),"latitude":x.get("latitude"),"longitude":x.get("longitude"),"special":True,"special_category":x.get("category", ""),"locality":x.get("address", "")} for x in list_special_zips()]
def haversine_m(lat1,lon1,lat2,lon2):
 r=6371000.0
 p1=math.radians(float(lat1));p2=math.radians(float(lat2));dp=math.radians(float(lat2)-float(lat1));dl=math.radians(float(lon2)-float(lon1))
 a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))
def near_special_location(lat,lon,radius_m=100.0):
 for x in list_special_zips():
  try:
   if haversine_m(lat,lon,x.get("latitude"),x.get("longitude"))<=radius_m:return True
  except (TypeError,ValueError):continue
 return False
def requested_address_from_note(note,grid_id):
 for line in str(note or "").splitlines():
  if line.lower().startswith("requested address:"):
   value=line.split(":",1)[1].strip()
   if value:return value
 return grid_id
def build_address_record(grid_id,state,postal,sub,address,approval_method):
 rec={"grid_id":grid_id,"address":address or grid_id,"display_name":address or grid_id,"latitude":sub["lat"],"longitude":sub["lon"],"address_type":sub.get("building_type","other"),"state_code":state["state_code"],"state_name":state["state_name"],"grid_prefix":state.get("grid_prefix",""),"postal_prefix":state["postal_prefix"],"created_from":"address_application","approval_method":approval_method,"submission_id":sub["id"],"created_at":time.time()}
 if postal:rec.update({"zip_code":postal["zip_code"],"postal_region":postal["region"],"postal_zone":postal.get("name","")})
 return rec
@app.get("/health")
def health():return {"status":"ok","records":len(addresses),"address_approval":"hybrid-confidence-v1"}
@app.get("/geography/states")
def geography_states():return state_feature_collection()
@app.get("/geography/zips")
def geography_zips():
 base=zip_feature_collection();base["features"].extend(manual_zip_features()["features"]);return base
@app.get("/geography/special-zips")
def geography_special_zips():return special_zip_features()
@app.get("/geography/status")
def geography_status():return validation_status()
@app.get("/coordinates/lookup")
def coordinate_lookup(lat:float=Query(...),lon:float=Query(...),tolerance_m:float=Query(default=15.0,ge=0.0,le=500.0)):
 state=state_for_coordinate(lat,lon)
 if not state:raise HTTPException(status_code=400,detail="Coordinates are outside the validated Uganda state polygons")
 if state.get("ambiguous"):raise HTTPException(status_code=409,detail="Coordinate lies on an ambiguous state boundary")
 postal=resolve_zip(lat,lon)
 candidates=[]
 for a in addresses:
  alat=a.get("latitude");alon=a.get("longitude")
  if alat is None or alon is None:continue
  try:d=haversine_m(lat,lon,alat,alon)
  except (TypeError,ValueError):continue
  candidates.append((d,a))
 candidates.sort(key=lambda x:x[0]);nearest=candidates[0] if candidates else None
 result={"latitude":lat,"longitude":lon,"matched":False,"created":False,"tolerance_m":tolerance_m,"state":state,"postal":postal,"assignment_required":True}
 if nearest is not None and nearest[0]<=tolerance_m:
  result.update({"matched":True,"assignment_required":False,"address":{**nearest[1],"distance_m":round(nearest[0],2)}})
 elif nearest:
  result["nearest_address"]={**nearest[1],"distance_m":round(nearest[0],2)}
 return result
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
@app.get("/admin/special-zips/categories")
def admin_special_zip_categories(x_admin_passcode:str=Header(default="")):check_admin(x_admin_passcode);return {"results":special_zip_catalog()}
@app.get("/admin/special-zips")
def admin_special_zips(x_admin_passcode:str=Header(default="")):check_admin(x_admin_passcode);return {"results":list_special_zips()}
@app.post("/admin/special-zips")
def admin_create_special_zip(payload:dict,x_admin_passcode:str=Header(default="")):
 check_admin(x_admin_passcode)
 try:return create_special_zip(payload.get("category"),payload.get("name"),payload.get("latitude"),payload.get("longitude"),payload.get("address",""),payload.get("notes",""),payload.get("zip_code"))
 except (ValueError,TypeError) as e:raise HTTPException(status_code=400,detail=str(e))
@app.delete("/admin/special-zips/{zip_code}")
def admin_delete_special_zip(zip_code:str,x_admin_passcode:str=Header(default="")):
 check_admin(x_admin_passcode)
 if not delete_special_zip(zip_code):raise HTTPException(status_code=404,detail="Special ZIP assignment not found")
 return {"deleted":True,"zip_code":str(zip_code).zfill(5)}
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
@app.get("/admin-zip-link.js")
def admin_zip_link_js():return FileResponse(ADMIN_ZIP_LINK_FILE,media_type="application/javascript; charset=utf-8",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
@app.get("/admin")
def admin_page():
 with open(ADMIN_FILE,"r",encoding="utf-8") as f:html=f.read()
 script='<script src="/admin-zip-link.js"></script>'
 html=html.replace("</body>",script+"</body>") if "</body>" in html else html+script
 return Response(content=html,media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
@app.get("/admin/zips")
def zip_admin_page():return FileResponse(ZIP_ADMIN_FILE,media_type="text/html")
@app.get("/admin/special-zips/manage")
def special_zip_admin_page():return FileResponse(SPECIAL_ZIP_ADMIN_FILE,media_type="text/html")
@app.get("/ship")
def ship_page():return FileResponse(SHIP_FILE,media_type="text/html")
@app.get("/driver")
def driver_page():return FileResponse(DRIVER_FILE,media_type="text/html")
@app.get("/test-tool")
def test_tool_page():return FileResponse(TEST_TOOL_FILE,media_type="text/html")
@app.get("/submit")
def submit_page():return FileResponse(SUBMIT_FILE,media_type="text/html")
@app.get("/review")
def review_page():return FileResponse(REVIEW_FILE,media_type="text/html")
@app.get("/search")
def search(q:str=Query(...,min_length=1)):
 x=q.strip().lower();normal=[a for a in addresses if x in str(a.get("grid_id","")).lower() or x in str(a.get("address","")).lower()]
 special=[a for a in special_zip_search_records() if x in str(a.get("zip_code","")).lower() or x in str(a.get("address","")).lower() or x in str(a.get("locality","")).lower()]
 r=(special+normal)[:50];return {"count":len(r),"results":r}
@app.get("/address/{grid_id}")
def get_address(grid_id:str):
 key=grid_id.strip().lower()
 for s in special_zip_search_records():
  if str(s.get("zip_code","")).strip().lower()==key:return s
 for a in addresses:
  if str(a.get("grid_id","")).strip().lower()==key:return a
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
async def create_submission(lat:float=Form(...),lon:float=Form(...),building_type:str=Form(...),note:str=Form(""),gps_accuracy_m:float=Form(None),file:UploadFile=File(None)):
 building_type=building_type.strip().lower()
 if building_type not in VALID_BUILDING_TYPES:raise HTTPException(status_code=400,detail="Invalid building type")
 state=state_for_coordinate(lat,lon)
 if not state:raise HTTPException(status_code=400,detail="Coordinates are outside the validated Uganda state polygons")
 postal=resolve_zip(lat,lon)
 confidence=evaluate_address_application(lat,lon,addresses,state,postal,gps_accuracy_m=gps_accuracy_m,is_special=near_special_location(lat,lon))
 s={"id":str(uuid.uuid4()),"lat":lat,"lon":lon,"building_type":building_type,"note":note[:300],"status":"pending","created_at":time.time(),"gps_accuracy_m":gps_accuracy_m,"confidence_score":confidence["score"],"confidence_decision":confidence["decision"],"confidence_reasons":confidence["reasons"]}
 store_create_submission(s)
 if confidence["auto_approve"]:
  grid_id,assigned_state=next_grid_id(addresses,lat,lon);assigned_address=requested_address_from_note(note,grid_id)
  rec=build_address_record(grid_id,assigned_state,postal,s,assigned_address,"auto_confidence")
  save_addresses(addresses+[rec])
  s=store_update_submission(s["id"],status="approved",assigned_grid_id=grid_id,assigned_address=assigned_address,assigned_zip_code=postal.get("zip_code") if postal else None,approval_method="auto_confidence",reviewed_at=time.time()) or s
  s["address"] = rec
  s["message"] = "UGAMAP VERIFIED — Automatically Assigned"
 else:
  s["message"] = "Application received — Admin review required"
 s["confidence"] = confidence
 return s
@app.get("/submissions")
def list_submissions(status:str=Query(default=""),x_admin_passcode:str=Header(default="")):
 check_admin(x_admin_passcode);items=store_list_submissions(status);return {"count":len(items),"results":items}
@app.post("/submissions/{submission_id}/decision")
def decide_submission(submission_id:str,action:str=Form(...),grid_id:str=Form(""),address:str=Form(""),x_admin_passcode:str=Header(default="")):
 check_admin(x_admin_passcode);sub=store_get_submission(submission_id)
 if not sub:raise HTTPException(status_code=404,detail="Submission not found")
 if sub.get("status")=="approved":raise HTTPException(status_code=409,detail="Submission is already approved")
 action=action.strip().lower()
 if action=="deny":return store_update_submission(submission_id,status="denied",approval_method="admin_denied",reviewed_at=time.time())
 if action not in {"approve","approved"}:raise HTTPException(status_code=400,detail="Action must be approve or deny")
 assigned_grid_id,state=next_grid_id(addresses,sub["lat"],sub["lon"]);postal=resolve_zip(sub["lat"],sub["lon"]);assigned_address=address.strip() or requested_address_from_note(sub.get("note",""),assigned_grid_id)
 rec=build_address_record(assigned_grid_id,state,postal,sub,assigned_address,"admin_review")
 save_addresses(addresses+[rec])
 return store_update_submission(submission_id,status="approved",assigned_grid_id=assigned_grid_id,assigned_address=assigned_address,assigned_zip_code=postal.get("zip_code") if postal else None,approval_method="admin_review",reviewed_at=time.time())

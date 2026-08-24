from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import time
import uuid

from data_hub import router as data_hub_router
from mailing import router as mailing_router
import shipments
from shipments import router as shipments_router

app = FastAPI(title="Uganda National Grid API", version="1.6")
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
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)
except Exception:
    addresses = []

REPORTS = []
REPORT_TTL_SECONDS = 6 * 3600
VALID_CATEGORIES = {"police", "accident", "road_closure", "bridge", "traffic", "weather"}

SUBMISSIONS = []
VALID_BUILDING_TYPES = {"hospital", "police", "government", "residence", "business", "other"}
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime", "video/webm"}
MAX_MEDIA_BYTES = 15 * 1024 * 1024


def prune_reports():
    now = time.time()
    global REPORTS
    REPORTS = [r for r in REPORTS if now - r["created_at"] < REPORT_TTL_SECONDS]


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


# --- Wire up routers ---
# Shipments needs a way to read the current `addresses` list for distance
# lookups without a circular import, so we hand it a zero-arg getter.
shipments.register_rate_routes(lambda: addresses)
app.include_router(shipments_router)
app.include_router(mailing_router)
app.include_router(data_hub_router)


@app.get("/health")
def health():
    return {"status": "ok", "records": len(addresses)}


@app.api_route("/", methods=["GET", "HEAD"])
def home():
    if not os.path.exists(INDEX_FILE):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_FILE, media_type="text/html")


@app.get("/app.js")
def app_js():
    if not os.path.exists(APP_JS_FILE):
        raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(
        APP_JS_FILE,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@app.get("/submit")
def submit_page():
    if not os.path.exists(SUBMIT_FILE):
        raise HTTPException(status_code=404, detail="submit.html not found")
    return FileResponse(SUBMIT_FILE, media_type="text/html")


@app.get("/review")
def review_page():
    if not os.path.exists(REVIEW_FILE):
        raise HTTPException(status_code=404, detail="review.html not found")
    return FileResponse(REVIEW_FILE, media_type="text/html")


@app.get("/admin")
def admin_page():
    if not os.path.exists(ADMIN_FILE):
        raise HTTPException(status_code=404, detail="admin.html not found")
    return FileResponse(ADMIN_FILE, media_type="text/html")


@app.get("/search")
def search(q: str = Query(..., min_length=1)):
    query = q.strip().lower()
    if not query:
        return {"count": 0, "results": []}
    results = []
    for item in addresses:
        grid_id = str(item.get("grid_id", "")).strip().lower()
        address = str(item.get("address", "")).strip().lower()
        if query in grid_id or query in address:
            results.append(item)
        if len(results) >= 50:
            break
    return {"count": len(results), "results": results}


@app.get("/address/{grid_id}")
def get_address(grid_id: str):
    search_id = grid_id.strip().lower()
    for item in addresses:
        stored_id = str(item.get("grid_id", "")).strip().lower()
        if stored_id == search_id:
            return item
    raise HTTPException(status_code=404, detail="Address not found")


@app.get("/stats")
def stats():
    return {
        "total_records": len(addresses),
        "database": "entebbe_database.json",
        "frontend": "index.html + app.js",
    }


@app.post("/report")
async def create_report(
    category: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    note: str = Form(""),
    file: UploadFile = File(None),
):
    category = category.strip().lower()
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    prune_reports()

    media_url = ""
    media_type = ""
    if file is not None and file.filename:
        if file.content_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        contents = await file.read()
        if len(contents) > MAX_MEDIA_BYTES:
            raise HTTPException(status_code=400, detail="File too large (max 15MB)")
        ext = os.path.splitext(file.filename)[1][:10]
        filename = str(uuid.uuid4()) + ext
        filepath = os.path.join(UPLOADS_DIR, filename)
        with open(filepath, "wb") as out:
            out.write(contents)
        media_url = "/uploads/" + filename
        media_type = file.content_type

    report = {
        "id": str(uuid.uuid4()),
        "category": category,
        "lat": lat,
        "lon": lon,
        "note": note.strip()[:200],
        "media_url": media_url,
        "media_type": media_type,
        "created_at": time.time(),
    }
    REPORTS.append(report)
    return report


@app.get("/reports")
def list_reports():
    prune_reports()
    return {"count": len(REPORTS), "results": REPORTS}


@app.post("/submissions")
async def create_submission(
    lat: float = Form(...),
    lon: float = Form(...),
    building_type: str = Form(...),
    note: str = Form(""),
    file: UploadFile = File(None),
):
    building_type = building_type.strip().lower()
    if building_type not in VALID_BUILDING_TYPES:
        raise HTTPException(status_code=400, detail="Invalid building type")

    media_url = ""
    media_type = ""
    if file is not None and file.filename:
        if file.content_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        contents = await file.read()
        if len(contents) > MAX_MEDIA_BYTES:
            raise HTTPException(status_code=400, detail="File too large (max 15MB)")
        ext = os.path.splitext(file.filename)[1][:10]
        filename = str(uuid.uuid4()) + ext
        filepath = os.path.join(UPLOADS_DIR, filename)
        with open(filepath, "wb") as out:
            out.write(contents)
        media_url = "/uploads/" + filename
        media_type = file.content_type

    submission = {
        "id": str(uuid.uuid4()),
        "lat": lat,
        "lon": lon,
        "building_type": building_type,
        "note": note.strip()[:300],
        "media_url": media_url,
        "media_type": media_type,
        "status": "pending",
        "assigned_grid_id": "",
        "assigned_address": "",
        "created_at": time.time(),
    }
    SUBMISSIONS.append(submission)
    return submission


@app.get("/submissions")
def list_submissions(status: str = Query(default=""), x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    items = SUBMISSIONS
    if status:
        items = [s for s in items if s["status"] == status]
    return {"count": len(items), "results": list(reversed(items))}


@app.post("/submissions/{submission_id}/decision")
def decide_submission(
    submission_id: str,
    action: str = Form(...),
    grid_id: str = Form(""),
    address: str = Form(""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    action = action.strip().lower()
    if action not in {"approve", "deny"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    sub = next((s for s in SUBMISSIONS if s["id"] == submission_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    if action == "deny":
        sub["status"] = "denied"
        return sub

    grid_id = grid_id.strip()
    address = address.strip()
    if not grid_id or not address:
        raise HTTPException(status_code=400, detail="grid_id and address are required to approve")

    sub["status"] = "approved"
    sub["assigned_grid_id"] = grid_id
    sub["assigned_address"] = address
    addresses.append({
        "grid_id": grid_id,
        "address": address,
        "latitude": sub["lat"],
        "longitude": sub["lon"],
    })
    return sub

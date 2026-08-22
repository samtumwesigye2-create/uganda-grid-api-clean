from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os
import time
import uuid

app = FastAPI(title="Uganda National Grid API", version="1.4")
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
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)
except Exception:
    addresses = []

REPORTS = []
REPORT_TTL_SECONDS = 6 * 3600
CONFIRM_EXTEND_SECONDS = 3 * 3600
DISMISS_THRESHOLD = 3
VALID_CATEGORIES = {"police", "accident", "road_closure", "bridge", "traffic", "weather"}
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime", "video/webm"}
MAX_MEDIA_BYTES = 15 * 1024 * 1024

class ConfirmIn(BaseModel):
    vote: str

def prune_reports():
    now = time.time()
    global REPORTS
    REPORTS = [r for r in REPORTS if now - r["created_at"] < REPORT_TTL_SECONDS]

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
    return FileResponse(APP_JS_FILE, media_type="application/javascript; charset=utf-8")

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
        "confirm_count": 0,
        "dismiss_count": 0,
    }
    REPORTS.append(report)
    return report

@app.post("/report/{report_id}/confirm")
def confirm_report(report_id: str, payload: ConfirmIn):
    prune_reports()
    vote = payload.vote.strip().lower()
    if vote not in {"confirm", "dismiss"}:
        raise HTTPException(status_code=400, detail="Invalid vote")
    target = None
    for r in REPORTS:
        if r["id"] == report_id:
            target = r
            break
    if not target:
        raise HTTPException(status_code=404, detail="Report not found")

    if vote == "confirm":
        target["confirm_count"] += 1
        target["created_at"] = max(target["created_at"], time.time() - (REPORT_TTL_SECONDS - CONFIRM_EXTEND_SECONDS))
    else:
        target["dismiss_count"] += 1
        if target["dismiss_count"] - target["confirm_count"] >= DISMISS_THRESHOLD:
            REPORTS[:] = [r for r in REPORTS if r["id"] != report_id]
            return {"removed": True, "id": report_id}

    return target

@app.get("/reports")
def list_reports():
    prune_reports()
    return {"count": len(REPORTS), "results": REPORTS}

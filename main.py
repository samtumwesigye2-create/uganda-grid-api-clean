from fastapi import FastAPI,from auth_middleware import PasscodeMiddleware
 Query, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os
import time
import uuid
import urllib.request
import urllib.parse
import hashlib
import secrets

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
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
USERS_FILE = os.path.join(BASE_DIR, "users.json")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

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

try:
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        USERS = json.load(f)
except Exception:
    USERS = {}

SESSIONS = {}


def save_users():
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(USERS, f)
    except Exception as e:
        print("Failed to save users:", e)


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return digest, salt


def verify_password(password, salt, digest):
    check, _ = hash_password(password, salt)
    return secrets.compare_digest(check, digest)


def make_session(email):
    token = secrets.token_hex(32)
    SESSIONS[token] = email
    return token


def get_session_email(token):
    return SESSIONS.get(token)


def public_user(record):
    return {
        "name": record.get("name", ""),
        "email": record.get("email", ""),
        "phone": record.get("phone", ""),
        "address": record.get("address", ""),
    }


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


# ---------------------------------------------------------------------
# User accounts (signup / login / profile)
# ---------------------------------------------------------------------

class SignupIn(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""
    address: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileUpdateIn(BaseModel):
    token: str
    name: str = ""
    phone: str = ""
    address: str = ""


@app.post("/auth/signup")
def signup(body: SignupIn):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if email in USERS:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    digest, salt = hash_password(body.password)
    record = {
        "name": name[:100],
        "email": email,
        "phone": body.phone.strip()[:30],
        "address": body.address.strip()[:200],
        "password_hash": digest,
        "password_salt": salt,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    USERS[email] = record
    save_users()
    token = make_session(email)
    return {"token": token, **public_user(record)}


@app.post("/auth/login")
def login(body: LoginIn):
    email = body.email.strip().lower()
    record = USERS.get(email)
    if not record or not verify_password(
        body.password, record.get("password_salt", ""), record.get("password_hash", "")
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = make_session(email)
    return {"token": token, **public_user(record)}


@app.post("/auth/logout")
def logout(token: str = Form(...)):
    SESSIONS.pop(token, None)
    return {"ok": True}


@app.get("/auth/me")
def me(token: str = Query(...)):
    email = get_session_email(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    record = USERS.get(email)
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    return public_user(record)


@app.post("/profile")
def update_profile(body: ProfileUpdateIn):
    email = get_session_email(body.token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    record = USERS.get(email)
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name.strip():
        record["name"] = body.name.strip()[:100]
    record["phone"] = body.phone.strip()[:30]
    record["address"] = body.address.strip()[:200]
    record["updated_at"] = time.time()
    USERS[email] = record
    save_users()
    return public_user(record)


# ---------------------------------------------------------------------
# Trending news (requires a free NEWS_API_KEY from gnews.io set as an
# environment variable on Railway/Render; without it, returns a
# friendly "not configured" response instead of failing).
# ---------------------------------------------------------------------

@app.get("/news")
def get_news(region: str = Query(default="Uganda")):
    if not NEWS_API_KEY:
        return {
            "available": False,
            "message": "News feed not configured yet. Add a NEWS_API_KEY environment variable to enable this.",
            "articles": [],
        }
    try:
        query = urllib.parse.quote(f"{region} Uganda")
        url = (
            "https://gnews.io/api/v4/search"
            f"?q={query}&lang=en&max=8&sortby=publishedAt&token={NEWS_API_KEY}"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        articles = [
            {
                "title": a.get("title", ""),
                "source": (a.get("source") or {}).get("name", ""),
                "url": a.get("url", ""),
                "publishedAt": a.get("publishedAt", ""),
            }
            for a in data.get("articles", [])[:8]
        ]
        return {"available": True, "articles": articles}
    except Exception:
        return {
            "available": False,
            "message": "Unable to fetch news right now. Try again shortly.",
            "articles": [],
        }
from mailing import router as mailing_router
from shipments import router as shipments_router
from fastapi.responses import FileResponse

app.include_router(mailing_router)
app.include_router(shipments_router)

from pathlib import Path

@app.get("/admin")
def admin_page():
    return FileResponse(Path(__file__).parent / "admin.html")

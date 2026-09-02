import os
import re
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, HTTPException, Header, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")
router = APIRouter()

ALLOWED_TYPES = {"schedule_pickup", "hold_delivery", "change_address", "po_box", "delivery_alerts"}
PO_BOX_STATUSES = {"pending", "changes_requested", "approved", "rejected"}
PO_BOX_SIZES = {"small", "medium", "large", "business"}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("""
      CREATE TABLE IF NOT EXISTS customer_service_requests (
        id TEXT PRIMARY KEY,
        request_type TEXT NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        tracking_number TEXT,
        address TEXT,
        details TEXT,
        status TEXT NOT NULL,
        created_at REAL NOT NULL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS po_box_applications (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        physical_address TEXT NOT NULL,
        normalized_address TEXT NOT NULL,
        grid_id TEXT,
        preferred_branch TEXT NOT NULL,
        box_size TEXT NOT NULL,
        business_name TEXT,
        notes TEXT,
        status TEXT NOT NULL,
        admin_note TEXT,
        assigned_po_box TEXT,
        revision INTEGER NOT NULL DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
      )
    """)
    c.execute("""
      CREATE TABLE IF NOT EXISTS po_boxes (
        po_box TEXT PRIMARY KEY,
        application_id TEXT NOT NULL UNIQUE,
        holder_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        physical_address TEXT NOT NULL,
        normalized_address TEXT NOT NULL UNIQUE,
        grid_id TEXT,
        branch TEXT NOT NULL,
        box_size TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at REAL NOT NULL,
        FOREIGN KEY(application_id) REFERENCES po_box_applications(id)
      )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_po_box_app_status ON po_box_applications(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_po_box_app_address ON po_box_applications(normalized_address)")
    c.commit()
    return c


def _require_admin(code: str):
    if code != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid admin passcode")


def _norm(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _branch_code(branch: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", branch or "")
    if not words:
        return "UG"
    if len(words) == 1:
        return words[0][:3].upper().ljust(3, "X")
    return "".join(w[0] for w in words[:3]).upper().ljust(3, "X")


def _next_po_box(c, branch: str) -> str:
    prefix = f"UG-PO-{_branch_code(branch)}-"
    rows = c.execute("SELECT po_box FROM po_boxes WHERE po_box LIKE ? ORDER BY po_box DESC LIMIT 1", (prefix + "%",)).fetchall()
    last = 0
    for row in rows:
        m = re.search(r"(\d+)$", row["po_box"])
        if m:
            last = max(last, int(m.group(1)))
    candidate = last + 1
    while True:
        po_box = f"{prefix}{candidate:06d}"
        exists = c.execute("SELECT 1 FROM po_boxes WHERE po_box = ?", (po_box,)).fetchone()
        if not exists:
            return po_box
        candidate += 1


@router.post("/customer-tools/request")
def create_customer_request(
    request_type: str = Form(...),
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    tracking_number: str = Form(""),
    address: str = Form(""),
    details: str = Form(""),
):
    request_type = request_type.strip().lower()
    if request_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported request type")
    if request_type == "po_box":
        raise HTTPException(status_code=400, detail="Use the dedicated P.O. Box application form")
    if not (email.strip() or phone.strip()):
        raise HTTPException(status_code=400, detail="Email or phone is required")
    rid = "UG-REQ-" + uuid.uuid4().hex[:10].upper()
    c = _conn()
    c.execute(
        "INSERT INTO customer_service_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
        (rid, request_type, name.strip(), email.strip(), phone.strip(), tracking_number.strip().upper(), address.strip(), details.strip()[:1000], "received", time.time()),
    )
    c.commit(); c.close()
    return {"request_id": rid, "status": "received", "request_type": request_type}


@router.get("/customer-tools/request/{request_id}")
def get_customer_request(request_id: str):
    c = _conn()
    row = c.execute("SELECT id, request_type, status, created_at FROM customer_service_requests WHERE id = ?", (request_id.strip().upper(),)).fetchone()
    c.close()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return dict(row)


@router.post("/po-box/apply")
def apply_for_po_box(
    name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    physical_address: str = Form(...),
    grid_id: str = Form(""),
    preferred_branch: str = Form(...),
    box_size: str = Form("small"),
    business_name: str = Form(""),
    notes: str = Form(""),
):
    name = name.strip()
    email = email.strip().lower()
    phone = phone.strip()
    physical_address = physical_address.strip()
    grid_id = grid_id.strip().upper()
    preferred_branch = preferred_branch.strip()
    box_size = box_size.strip().lower()
    if not name or not physical_address or not preferred_branch:
        raise HTTPException(status_code=400, detail="Name, physical address and preferred branch are required")
    if not (email or phone):
        raise HTTPException(status_code=400, detail="Email or phone is required")
    if box_size not in PO_BOX_SIZES:
        raise HTTPException(status_code=400, detail="Invalid P.O. Box size")

    normalized = _norm(physical_address)
    c = _conn()
    existing_box = c.execute("SELECT po_box FROM po_boxes WHERE normalized_address = ? AND status = 'active'", (normalized,)).fetchone()
    if existing_box:
        c.close()
        raise HTTPException(status_code=409, detail=f"This address already has active P.O. Box {existing_box['po_box']}")
    existing_app = c.execute(
        "SELECT id, status FROM po_box_applications WHERE normalized_address = ? AND status IN ('pending','changes_requested','approved') ORDER BY created_at DESC LIMIT 1",
        (normalized,),
    ).fetchone()
    if existing_app:
        c.close()
        raise HTTPException(status_code=409, detail=f"A P.O. Box application already exists for this address: {existing_app['id']} ({existing_app['status']})")

    app_id = "UG-POA-" + uuid.uuid4().hex[:10].upper()
    now = time.time()
    c.execute(
        """INSERT INTO po_box_applications
        (id,name,email,phone,physical_address,normalized_address,grid_id,preferred_branch,box_size,business_name,notes,status,admin_note,assigned_po_box,revision,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (app_id, name, email, phone, physical_address, normalized, grid_id, preferred_branch, box_size,
         business_name.strip(), notes.strip()[:1500], "pending", "", "", 1, now, now),
    )
    c.commit(); c.close()
    return {"application_id": app_id, "status": "pending", "message": "P.O. Box application submitted for administrative review"}


@router.get("/po-box/application/{application_id}")
def get_po_box_application(application_id: str, contact: str = Query(default="")):
    c = _conn()
    row = c.execute("SELECT * FROM po_box_applications WHERE id = ?", (application_id.strip().upper(),)).fetchone()
    c.close()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    d = dict(row)
    if contact:
        key = contact.strip().lower()
        if key not in {(d.get("email") or "").lower(), (d.get("phone") or "").lower()}:
            raise HTTPException(status_code=403, detail="Contact information does not match this application")
    return {
        "application_id": d["id"], "status": d["status"], "admin_note": d["admin_note"],
        "assigned_po_box": d["assigned_po_box"], "preferred_branch": d["preferred_branch"],
        "box_size": d["box_size"], "physical_address": d["physical_address"], "grid_id": d["grid_id"],
        "revision": d["revision"], "updated_at": d["updated_at"]
    }


@router.post("/po-box/application/{application_id}/revise")
def revise_po_box_application(
    application_id: str,
    contact: str = Form(...),
    physical_address: str = Form(...),
    grid_id: str = Form(""),
    preferred_branch: str = Form(...),
    box_size: str = Form("small"),
    business_name: str = Form(""),
    notes: str = Form(""),
):
    c = _conn()
    row = c.execute("SELECT * FROM po_box_applications WHERE id = ?", (application_id.strip().upper(),)).fetchone()
    if not row:
        c.close(); raise HTTPException(status_code=404, detail="Application not found")
    d = dict(row)
    key = contact.strip().lower()
    if key not in {(d.get("email") or "").lower(), (d.get("phone") or "").lower()}:
        c.close(); raise HTTPException(status_code=403, detail="Contact information does not match this application")
    if d["status"] != "changes_requested":
        c.close(); raise HTTPException(status_code=409, detail="This application is not awaiting changes")
    normalized = _norm(physical_address)
    duplicate = c.execute("SELECT po_box FROM po_boxes WHERE normalized_address = ? AND status = 'active'", (normalized,)).fetchone()
    if duplicate:
        c.close(); raise HTTPException(status_code=409, detail=f"This address already has active P.O. Box {duplicate['po_box']}")
    if box_size.strip().lower() not in PO_BOX_SIZES:
        c.close(); raise HTTPException(status_code=400, detail="Invalid P.O. Box size")
    c.execute("""UPDATE po_box_applications SET physical_address=?, normalized_address=?, grid_id=?, preferred_branch=?, box_size=?, business_name=?, notes=?, status='pending', admin_note='', revision=revision+1, updated_at=? WHERE id=?""",
              (physical_address.strip(), normalized, grid_id.strip().upper(), preferred_branch.strip(), box_size.strip().lower(), business_name.strip(), notes.strip()[:1500], time.time(), d["id"]))
    c.commit(); c.close()
    return {"application_id": d["id"], "status": "pending", "message": "Changes submitted for review"}


@router.get("/admin/po-box/applications")
def admin_list_po_box_applications(status: str = Query(default=""), x_admin_passcode: str = Header(default="")):
    _require_admin(x_admin_passcode)
    c = _conn()
    if status and status in PO_BOX_STATUSES:
        rows = c.execute("SELECT * FROM po_box_applications WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM po_box_applications ORDER BY created_at DESC").fetchall()
    out = [dict(r) for r in rows]
    c.close()
    return {"count": len(out), "results": out}


@router.get("/admin/po-box/registry")
def admin_po_box_registry(x_admin_passcode: str = Header(default="")):
    _require_admin(x_admin_passcode)
    c = _conn()
    rows = c.execute("SELECT * FROM po_boxes ORDER BY po_box").fetchall()
    out = [dict(r) for r in rows]
    c.close()
    return {"count": len(out), "results": out}


@router.post("/admin/po-box/applications/{application_id}/decision")
def admin_decide_po_box(
    application_id: str,
    action: str = Form(...),
    admin_note: str = Form(""),
    assigned_po_box: str = Form(""),
    x_admin_passcode: str = Header(default=""),
):
    _require_admin(x_admin_passcode)
    action = action.strip().lower()
    if action not in {"approve", "reject", "request_changes"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    c = _conn()
    row = c.execute("SELECT * FROM po_box_applications WHERE id=?", (application_id.strip().upper(),)).fetchone()
    if not row:
        c.close(); raise HTTPException(status_code=404, detail="Application not found")
    d = dict(row)
    if d["status"] == "approved":
        c.close(); raise HTTPException(status_code=409, detail="Application is already approved")

    if action == "reject":
        c.execute("UPDATE po_box_applications SET status='rejected', admin_note=?, updated_at=? WHERE id=?", (admin_note.strip(), time.time(), d["id"]))
        c.commit(); c.close()
        return {"application_id": d["id"], "status": "rejected"}

    if action == "request_changes":
        if not admin_note.strip():
            c.close(); raise HTTPException(status_code=400, detail="Explain what the customer must change")
        c.execute("UPDATE po_box_applications SET status='changes_requested', admin_note=?, updated_at=? WHERE id=?", (admin_note.strip(), time.time(), d["id"]))
        c.commit(); c.close()
        return {"application_id": d["id"], "status": "changes_requested"}

    existing_addr = c.execute("SELECT po_box FROM po_boxes WHERE normalized_address=? AND status='active'", (d["normalized_address"],)).fetchone()
    if existing_addr:
        c.close(); raise HTTPException(status_code=409, detail=f"Duplicate address blocked: already assigned {existing_addr['po_box']}")
    po_box = assigned_po_box.strip().upper() if assigned_po_box.strip() else _next_po_box(c, d["preferred_branch"])
    if c.execute("SELECT 1 FROM po_boxes WHERE po_box=?", (po_box,)).fetchone():
        c.close(); raise HTTPException(status_code=409, detail="That P.O. Box number is already assigned")
    now = time.time()
    c.execute("""INSERT INTO po_boxes
      (po_box,application_id,holder_name,email,phone,physical_address,normalized_address,grid_id,branch,box_size,status,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
      (po_box, d["id"], d["name"], d["email"], d["phone"], d["physical_address"], d["normalized_address"], d["grid_id"], d["preferred_branch"], d["box_size"], "active", now))
    c.execute("UPDATE po_box_applications SET status='approved', assigned_po_box=?, admin_note=?, updated_at=? WHERE id=?", (po_box, admin_note.strip(), now, d["id"]))
    c.commit(); c.close()
    return {"application_id": d["id"], "status": "approved", "po_box": po_box}

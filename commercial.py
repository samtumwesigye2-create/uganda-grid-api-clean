
"""
commercial.py — Commercial address registration.

Any building/location that requires more than one address (including
apartment buildings) is commercial. Commercial addresses can only be
registered by the landlord/company that owns the building, via an
application that an admin must approve — this is separate from the
existing citizen-facing building submission flow in main.py, which stays
residential-only.

On approval, one master address is created with a list of unit labels
attached directly to it (e.g. "Apt 1", "Suite 3B"). Units are NOT separate
searchable grid_id records — they only exist as labels under their master.
"""

import os
import sqlite3
import time
import uuid
from fastapi import APIRouter, Form, Header, HTTPException, Query, UploadFile, File

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_PROOF_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
MAX_PROOF_BYTES = 15 * 1024 * 1024

router = APIRouter()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS commercial_applications (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            applicant_name TEXT NOT NULL,
            applicant_phone TEXT NOT NULL,
            building_name TEXT,
            address_text TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            units TEXT NOT NULL,
            proof_url TEXT,
            status TEXT NOT NULL,
            assigned_grid_id TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS commercial_grid_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO commercial_grid_counter (id, next_number) VALUES (1, 1)"
    )
    conn.commit()
    conn.close()


init_db()


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


def next_commercial_grid_id():
    conn = get_conn()
    cur = conn.execute("SELECT next_number FROM commercial_grid_counter WHERE id = 1")
    n = cur.fetchone()["next_number"]
    conn.execute(
        "UPDATE commercial_grid_counter SET next_number = ? WHERE id = 1", (n + 1,)
    )
    conn.commit()
    conn.close()
    return f"UG-COM-{n:06d}"


def register_commercial_routes(addresses_ref, save_addresses_ref):
    """
    addresses_ref: zero-arg callable returning the current `addresses` list
    from main.py (avoids circular imports, same pattern as shipments.py).

    save_addresses_ref: callable(addresses_list) that persists the list back
    to disk (e.g. rewrites entebbe_database.json), so approved commercial
    addresses survive a restart and show up immediately in /search and
    /address/{grid_id}.
    """

    @router.post("/commercial/apply")
    async def apply_commercial(
        company_name: str = Form(...),
        applicant_name: str = Form(...),
        applicant_phone: str = Form(...),
        building_name: str = Form(""),
        address_text: str = Form(...),
        latitude: float = Form(...),
        longitude: float = Form(...),
        units: str = Form(...),  # comma-separated, e.g. "Apt 1, Apt 2, Suite 3B"
        proof: UploadFile = File(None),
    ):
        unit_list = [u.strip() for u in units.split(",") if u.strip()]
        if not unit_list:
            raise HTTPException(status_code=400, detail="At least one unit is required")

        proof_url = ""
        if proof is not None and proof.filename:
            if proof.content_type not in ALLOWED_PROOF_TYPES:
                raise HTTPException(status_code=400, detail="Unsupported file type")
            contents = await proof.read()
            if len(contents) > MAX_PROOF_BYTES:
                raise HTTPException(status_code=400, detail="File too large (max 15MB)")
            ext = os.path.splitext(proof.filename)[1][:10]
            filename = str(uuid.uuid4()) + ext
            filepath = os.path.join(UPLOADS_DIR, filename)
            with open(filepath, "wb") as out:
                out.write(contents)
            proof_url = "/uploads/" + filename

        application_id = str(uuid.uuid4())
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO commercial_applications
            (id, company_name, applicant_name, applicant_phone, building_name,
             address_text, latitude, longitude, units, proof_url, status,
             assigned_grid_id, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                application_id, company_name, applicant_name, applicant_phone,
                building_name, address_text, latitude, longitude,
                ",".join(unit_list), proof_url, "pending", "", time.time(),
            ),
        )
        conn.commit()
        conn.close()

        return {
            "id": application_id,
            "status": "pending",
            "unit_count": len(unit_list),
        }

    @router.get("/commercial/applications")
    def list_commercial_applications(
        status: str = Query(default=""),
        x_admin_passcode: str = Header(default=""),
    ):
        check_admin(x_admin_passcode)
        conn = get_conn()
        query = "SELECT * FROM commercial_applications"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {"count": len(rows), "results": [dict(r) for r in rows]}

    @router.post("/commercial/applications/{application_id}/decision")
    def decide_commercial_application(
        application_id: str,
        action: str = Form(...),
        x_admin_passcode: str = Header(default=""),
    ):
        check_admin(x_admin_passcode)
        action = action.strip().lower()
        if action not in {"approve", "deny"}:
            raise HTTPException(status_code=400, detail="Invalid action")

        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM commercial_applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Application not found")

        if action == "deny":
            conn.execute(
                "UPDATE commercial_applications SET status = 'denied' WHERE id = ?",
                (application_id,),
            )
            conn.commit()
            conn.close()
            return {"id": application_id, "status": "denied"}

        grid_id = next_commercial_grid_id()
        conn.execute(
            "UPDATE commercial_applications SET status = 'approved', assigned_grid_id = ? WHERE id = ?",
            (grid_id, application_id),
        )
        conn.commit()
        conn.close()

        unit_list = row["units"].split(",")
        addresses = addresses_ref()
        addresses.append({
            "grid_id": grid_id,
            "address": row["address_text"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "address_type": "commercial",
            "is_master": True,
            "building_name": row["building_name"],
            "company_name": row["company_name"],
            "units": unit_list,
        })
        save_addresses_ref(addresses)

        return {
            "id": application_id,
            "status": "approved",
            "grid_id": grid_id,
            "units": unit_list,
        }

    @router.get("/commercial/{grid_id}/units")
    def get_units(grid_id: str):
        addresses = addresses_ref()
        search_id = grid_id.strip().lower()
        for item in addresses:
            if str(item.get("grid_id", "")).strip().lower() == search_id:
                if item.get("address_type") != "commercial":
                    raise HTTPException(status_code=400, detail="Not a commercial address")
                return {
                    "grid_id": grid_id,
                    "building_name": item.get("building_name", ""),
                    "company_name": item.get("company_name", ""),
                    "units": item.get("units", []),
                }
        raise HTTPException(status_code=404, detail="Address not found")

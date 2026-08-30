"""
mailing.py — Email subscription list for shipping/delivery updates.

INSTALL: in main.py add:
    from mailing import router as mailing_router
    app.include_router(mailing_router)
"""

import os
import re
import sqlite3
import time
import uuid

from fastapi import APIRouter, Form, Header, HTTPException, Query

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mailing_list (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


@router.post("/mail/subscribe")
def subscribe(email: str = Form(...), name: str = Form("")):
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM mailing_list WHERE email = ?", (email,)
    ).fetchone()
    if existing:
        conn.close()
        return {"status": "already_subscribed", "email": email}

    subscriber_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO mailing_list (id, email, name, created_at) VALUES (?,?,?,?)",
        (subscriber_id, email, name.strip(), time.time()),
    )
    conn.commit()
    conn.close()
    return {"status": "subscribed", "email": email}


@router.get("/mail/list")
def list_subscribers(x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM mailing_list ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@router.delete("/mail/{email}")
def unsubscribe(email: str, x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    conn.execute("DELETE FROM mailing_list WHERE email = ?", (email.strip().lower(),))
    conn.commit()
    conn.close()
    return {"status": "removed", "email": email}

from __future__ import annotations

import os
import sqlite3
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
MASTER_DRIVER_ID = "UGATU-MASTER"


def master_key_configured() -> bool:
    return bool((os.environ.get("UGATU_MASTER_KEY") or "").strip())


def ensure_master_driver() -> bool:
    """Provision a dedicated master driver identity from an environment secret.

    The secret is never stored in source code. When UGATU_MASTER_KEY is not set,
    no master identity is created or changed.
    """
    key = (os.environ.get("UGATU_MASTER_KEY") or "").strip()
    if not key:
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS drivers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                passcode TEXT UNIQUE NOT NULL,
                vehicle_id TEXT,
                status TEXT NOT NULL DEFAULT 'off_duty',
                current_lat REAL,
                current_lon REAL,
                last_ping_at REAL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            )"""
        )
        conflict = conn.execute(
            "SELECT id FROM drivers WHERE passcode=? AND id!=?",
            (key, MASTER_DRIVER_ID),
        ).fetchone()
        if conflict:
            raise RuntimeError("UGATU_MASTER_KEY conflicts with an existing driver passcode")

        existing = conn.execute(
            "SELECT id FROM drivers WHERE id=?",
            (MASTER_DRIVER_ID,),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE drivers
                   SET name=?, phone=?, passcode=?, is_active=1
                   WHERE id=?""",
                ("UGATU Master", "SYSTEM", key, MASTER_DRIVER_ID),
            )
        else:
            conn.execute(
                """INSERT INTO drivers
                   (id,name,phone,passcode,vehicle_id,status,current_lat,current_lon,last_ping_at,is_active,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    MASTER_DRIVER_ID,
                    "UGATU Master",
                    "SYSTEM",
                    key,
                    None,
                    "available",
                    None,
                    None,
                    None,
                    1,
                    time.time(),
                ),
            )
        conn.commit()
        return True
    finally:
        conn.close()

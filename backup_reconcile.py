"""Automatic best-effort reconciliation into the independent backup service.

Runs in a daemon thread when imported by the production entrypoint.
UGASHIP shipments are mirrored from data_hub.db.
UGAMAP addresses are mirrored from entebbe_database.json when the file changes.
Backup failures never block production traffic.
"""

import json
import os
import sqlite3
import threading
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_SERVICE_URL = os.environ.get(
    "BACKUP_SERVICE_URL",
    "https://uga-backup-service-production.up.railway.app",
).rstrip("/")
BACKUP_SYNC_TOKEN = os.environ.get("BACKUP_SYNC_TOKEN", "").strip()
POLL_SECONDS = max(15, int(os.environ.get("BACKUP_RECONCILE_SECONDS", "30")))
SHIP_DB = os.path.join(BASE_DIR, "data_hub.db")
ADDRESS_FILE = os.path.join(BASE_DIR, "entebbe_database.json")

_started = False
_lock = threading.Lock()
_last_ship_fingerprint = None
_last_address_mtime = None
_previous_shipment_ids = set()


def _request(path: str, payload: dict, timeout: int = 20):
    if not BACKUP_SYNC_TOKEN:
        return None
    req = urllib.request.Request(
        f"{BACKUP_SERVICE_URL}{path}",
        data=json.dumps(payload, default=str).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-backup-token": BACKUP_SYNC_TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _bulk(source: str, entity_type: str, records: list[dict]):
    for i in range(0, len(records), 500):
        _request(
            "/sync/bulk",
            {
                "source": source,
                "entity_type": entity_type,
                "records": records[i : i + 500],
            },
            timeout=30,
        )


def _delete(source: str, entity_type: str, entity_id: str):
    _request(
        "/sync",
        {
            "source": source,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action": "delete",
            "data": {},
        },
    )


def _read_shipments():
    if not os.path.exists(SHIP_DB):
        return []
    conn = sqlite3.connect(SHIP_DB)
    conn.row_factory = sqlite3.Row
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shipments'"
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute("SELECT * FROM shipments ORDER BY created_at ASC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _sync_shipments():
    global _last_ship_fingerprint, _previous_shipment_ids
    rows = _read_shipments()
    fingerprint = tuple(
        sorted(
            (
                str(r.get("id", "")),
                str(r.get("shipment_number", "")),
                str(r.get("status", "")),
                str(r.get("delivery_status", "")),
                str(r.get("payment_ref", "")),
                str(r.get("payment_method", "")),
                str(r.get("pickup", "")),
                str(r.get("delivery", "")),
                str(r.get("weight_kg", "")),
                str(r.get("rate_ugx", "")),
            )
            for r in rows
        )
    )
    if fingerprint == _last_ship_fingerprint:
        return

    current_ids = {str(r.get("id") or r.get("shipment_number")) for r in rows}
    if rows:
        _bulk("UGASHIP", "shipment", rows)
    for deleted_id in _previous_shipment_ids - current_ids:
        _delete("UGASHIP", "shipment", deleted_id)

    _previous_shipment_ids = current_ids
    _last_ship_fingerprint = fingerprint


def _sync_addresses_if_changed():
    global _last_address_mtime
    if not os.path.exists(ADDRESS_FILE):
        return
    mtime = os.path.getmtime(ADDRESS_FILE)
    if _last_address_mtime == mtime:
        return

    with open(ADDRESS_FILE, "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    if not isinstance(rows, list):
        return

    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity_id = row.get("grid_id") or row.get("id")
        if entity_id is None:
            continue
        item = dict(row)
        item.setdefault("id", str(entity_id))
        normalized.append(item)

    if normalized:
        _bulk("UGAMAP", "address", normalized)
    _last_address_mtime = mtime


def _worker():
    while True:
        try:
            if BACKUP_SYNC_TOKEN:
                _sync_shipments()
                _sync_addresses_if_changed()
        except Exception as exc:
            print(f"[backup-reconcile] {type(exc).__name__}: {exc}")
        time.sleep(POLL_SECONDS)


def start_backup_reconciler():
    global _started
    with _lock:
        if _started:
            return
        _started = True
        thread = threading.Thread(target=_worker, name="uga-backup-reconcile", daemon=True)
        thread.start()


start_backup_reconciler()

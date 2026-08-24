"""
data_hub.py — Drop-in data collection & storage module for Uganda National Grid.
"""

import csv
import io
import json
import os
import sqlite3
import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")
ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "uganda2026")

router = APIRouter()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            form_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_form_type ON records(form_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON records(created_at)")
    conn.commit()
    conn.close()


init_db()


def check_admin(x_admin_passcode: str):
    if x_admin_passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=401, detail="Invalid passcode")


@router.post("/data/collect")
async def collect(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    form_type = str(body.pop("form_type", "")).strip().lower()
    if not form_type:
        raise HTTPException(status_code=400, detail="form_type is required")

    record_id = str(uuid.uuid4())
    conn = get_conn()
    conn.execute(
        "INSERT INTO records (id, form_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (record_id, form_type, json.dumps(body), time.time()),
    )
    conn.commit()
    conn.close()

    return {"id": record_id, "form_type": form_type, "status": "stored"}


@router.get("/data/records")
def list_records(
    form_type: str = Query(default=""),
    limit: int = Query(default=200, le=1000),
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    query = "SELECT * FROM records"
    params = []
    if form_type:
        query += " WHERE form_type = ?"
        params.append(form_type.strip().lower())
    query += f" ORDER BY created_at {'ASC' if sort == 'asc' else 'DESC'} LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append(
            {
                "id": r["id"],
                "form_type": r["form_type"],
                "payload": json.loads(r["payload"]),
                "created_at": r["created_at"],
            }
        )
    return {"count": len(results), "results": results}


@router.get("/data/export.csv")
def export_csv(
    form_type: str = Query(default=""),
    x_admin_passcode: str = Header(default=""),
):
    check_admin(x_admin_passcode)
    conn = get_conn()
    query = "SELECT * FROM records"
    params = []
    if form_type:
        query += " WHERE form_type = ?"
        params.append(form_type.strip().lower())
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    all_keys = set()
    parsed_rows = []
    for r in rows:
        payload = json.loads(r["payload"])
        parsed_rows.append((r, payload))
        all_keys.update(payload.keys())
    all_keys = sorted(all_keys)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "form_type", "created_at"] + all_keys)
    for r, payload in parsed_rows:
        writer.writerow(
            [r["id"], r["form_type"], r["created_at"]]
            + [payload.get(k, "") for k in all_keys]
        )
    buf.seek(0)

    filename = f"data_export_{form_type or 'all'}.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/data/stats")
def stats(x_admin_passcode: str = Header(default="")):
    check_admin(x_admin_passcode)
    conn = get_conn()
    rows = conn.execute("SELECT form_type, created_at FROM records").fetchall()
    conn.close()

    by_type = defaultdict(int)
    by_day = defaultdict(int)
    for r in rows:
        by_type[r["form_type"]] += 1
        day = time.strftime("%Y-%m-%d", time.localtime(r["created_at"]))
        by_day[day] += 1

    return {
        "total_records": len(rows),
        "by_form_type": dict(by_type),
        "by_day": dict(sorted(by_day.items())),
    }


@router.get("/data", response_class=HTMLResponse)
def data_page():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Data — Uganda National Grid</title>
<style>
  body { font-family: -apple-system, sans-serif; background:#0f1220; color:#eee; margin:0; padding:20px; }
  h1 { font-size: 20px; }
  input, select, button { padding:8px; border-radius:6px; border:1px solid #333; background:#1a1d2e; color:#eee; margin:4px 4px 4px 0; }
  button { background:#e2593a; border:none; cursor:pointer; }
  table { width:100%; border-collapse: collapse; margin-top:16px; font-size:13px; }
  th, td { border:1px solid #2a2d3e; padding:6px 8px; text-align:left; vertical-align:top; }
  th { background:#1a1d2e; cursor:pointer; }
  #passGate { max-width:320px; margin:80px auto; text-align:center; }
  #main { display:none; }
</style>
</head>
<body>

<div id="passGate">
  <h1>Admin Data</h1>
  <input id="pass" type="password" placeholder="Admin passcode" />
  <button onclick="unlock()">Enter</button>
</div>

<div id="main">
  <h1>Collected Data</h1>
  <div>
    <input id="filterType" placeholder="Filter by form_type (blank = all)" />
    <button onclick="load()">Refresh</button>
    <button onclick="exportCsv()">Export CSV</button>
  </div>
  <div id="statsBar" style="margin-top:10px; color:#aaa; font-size:13px;"></div>
  <table id="tbl">
    <thead><tr><th>Created</th><th>Type</th><th>Data</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<script>
let PASS = "";

function unlock() {
  PASS = document.getElementById('pass').value;
  document.getElementById('passGate').style.display = 'none';
  document.getElementById('main').style.display = 'block';
  load();
  loadStats();
}

async function load() {
  const type = document.getElementById('filterType').value.trim();
  const url = '/data/records' + (type ? ('?form_type=' + encodeURIComponent(type)) : '');
  const res = await fetch(url, { headers: { 'X-Admin-Passcode': PASS } });
  if (!res.ok) { alert('Wrong passcode or error loading data'); return; }
  const data = await res.json();
  const tbody = document.querySelector('#tbl tbody');
  tbody.innerHTML = '';
  data.results.forEach(r => {
    const tr = document.createElement('tr');
    const date = new Date(r.created_at * 1000).toLocaleString();
    tr.innerHTML = `<td>${date}</td><td>${r.form_type}</td><td><pre style="white-space:pre-wrap;margin:0;">${JSON.stringify(r.payload, null, 2)}</pre></td>`;
    tbody.appendChild(tr);
  });
}

async function loadStats() {
  const res = await fetch('/data/stats', { headers: { 'X-Admin-Passcode': PASS } });
  if (!res.ok) return;
  const s = await res.json();
  document.getElementById('statsBar').textContent =
    `Total: ${s.total_records} — By type: ` +
    Object.entries(s.by_form_type).map(([k,v]) => `${k}: ${v}`).join(', ');
}

function exportCsv() {
  const type = document.getElementById('filterType').value.trim();
  const url = '/data/export.csv' + (type ? ('?form_type=' + encodeURIComponent(type)) : '');
  fetch(url, { headers: { 'X-Admin-Passcode': PASS } })
    .then(res => res.blob())
    .then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'data_export.csv';
      a.click();
    });
}
</script>
</body>
</html>
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

app = FastAPI(title="Uganda National Grid API", version="1.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "entebbe_database.json")
INCIDENT_DB = os.path.join(BASE_DIR, "incidents.db")

try:
    with open(DATABASE, "r", encoding="utf-8") as file:
        addresses = json.load(file)
except Exception:
    addresses = []


def incident_conn():
    conn = sqlite3.connect(INCIDENT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        details TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


class Incident(BaseModel):
    type: str
    latitude: float
    longitude: float
    details: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():
    return r'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Uganda National Grid</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f4f6f8}header{background:#111827;color:#fff;padding:14px;text-align:center}header h1{margin:0;font-size:22px}.toolbar{background:#fff;padding:10px;display:flex;gap:6px;flex-wrap:wrap;justify-content:center;border-bottom:1px solid #ddd}.toolbar button{border:0;border-radius:8px;padding:9px 12px;font-weight:700;background:#e5e7eb}.toolbar button.active{background:#111827;color:#fff}#map{height:calc(100vh - 116px);min-height:520px}.incident-icon{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;border:3px solid white;box-shadow:0 1px 6px #555;background:#fff}.count{font-size:12px;margin-top:4px;color:#d1d5db}
</style></head>
<body><header><h1>🇺🇬 Uganda National Grid</h1><div class="count" id="count">Loading active road intelligence…</div></header>
<div class="toolbar"><button class="active" onclick="filterIncidents('all',this)">All</button><button onclick="filterIncidents('accident',this)">🚨 Accidents</button><button onclick="filterIncidents('police',this)">👮 Police</button><button onclick="filterIncidents('closure',this)">🚧 Closures</button><button onclick="filterIncidents('bridge',this)">🌉 Bridges</button></div>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map').setView([1.3733,32.2903],7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const incidentLayer=L.layerGroup().addTo(map);let incidents=[];let currentFilter='all';
const meta={accident:{emoji:'🚨',label:'Accident'},police:{emoji:'👮',label:'Police'},closure:{emoji:'🚧',label:'Road Closure'},bridge:{emoji:'🌉',label:'Bridge'},roundabout:{emoji:'🔄',label:'Roundabout'},highway:{emoji:'🛣️',label:'Highway'}};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function render(){incidentLayer.clearLayers();const shown=currentFilter==='all'?incidents:incidents.filter(x=>x.type===currentFilter);shown.forEach(x=>{const m=meta[x.type]||{emoji:'⚠️',label:x.type};const icon=L.divIcon({className:'',html:`<div class="incident-icon">${m.emoji}</div>`,iconSize:[34,34],iconAnchor:[17,17]});L.marker([x.latitude,x.longitude],{icon}).addTo(incidentLayer).bindPopup(`<strong>${esc(m.label)}</strong><br>${esc(x.details||'No details')}<br><small>${esc(x.created_at||'')}</small>`);});document.getElementById('count').textContent=`${shown.length} active map item${shown.length===1?'':'s'} displayed`;}
function filterIncidents(type,btn){currentFilter=type;document.querySelectorAll('.toolbar button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');render();}
async function loadIncidents(){try{const r=await fetch('/incidents?status=active');if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json();incidents=Array.isArray(d.incidents)?d.incidents:[];render();}catch(e){console.error(e);document.getElementById('count').textContent='Unable to load road intelligence';}}
loadIncidents();setInterval(loadIncidents,30000);
</script></body></html>'''


@app.get("/search")
def search(q: str = Query(...)):
    q = q.strip().lower()
    results = [item for item in addresses if q in json.dumps(item).lower()]
    return {"count": len(results), "results": results[:50]}


@app.get("/address/{grid_id}")
def get_address(grid_id: str):
    search_id = grid_id.strip()
    for item in addresses:
        if str(item.get("grid_id", "")).strip() == search_id:
            return item
    return {"error": "Address not found", "searched": search_id}


@app.get("/stats")
def stats():
    return {"total_records": len(addresses), "database": "entebbe_database.json"}


@app.get("/incidents")
def list_incidents(status: str = "active"):
    conn = incident_conn()
    try:
        rows = conn.execute("SELECT id,type,latitude,longitude,details,status,created_at FROM incidents WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        return {"count": len(rows), "incidents": [dict(row) for row in rows]}
    finally:
        conn.close()


@app.post("/incidents")
def create_incident(payload: Incident):
    allowed = {"accident", "police", "closure", "bridge", "roundabout", "highway"}
    if payload.type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid incident type")
    if not (-90 <= payload.latitude <= 90 and -180 <= payload.longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")
    incident_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    conn = incident_conn()
    try:
        conn.execute("INSERT INTO incidents(id,type,latitude,longitude,details,status,created_at) VALUES(?,?,?,?,?,?,?)", (incident_id,payload.type,payload.latitude,payload.longitude,payload.details[:500],"active",created_at))
        conn.commit()
        return {"id":incident_id,"type":payload.type,"latitude":payload.latitude,"longitude":payload.longitude,"details":payload.details[:500],"status":"active","created_at":created_at}
    finally:
        conn.close()


@app.patch("/incidents/{incident_id}")
def close_incident(incident_id: str):
    conn = incident_conn()
    try:
        cur = conn.execute("UPDATE incidents SET status='closed' WHERE id=?", (incident_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"id": incident_id, "status": "closed"}
    finally:
        conn.close()

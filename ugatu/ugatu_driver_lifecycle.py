from __future__ import annotations

import os, sqlite3, time, uuid
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/ugatu/driver-lifecycle', tags=['UGATU Driver Lifecycle'])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data_hub.db')
FINAL = {'completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse'}

class ShiftStartIn(BaseModel):
    start_odometer: float | None = Field(default=None, ge=0)
    notes: str = ''

class ShiftReconcileIn(BaseModel):
    end_odometer: float | None = Field(default=None, ge=0)
    notes: str = ''

class LegStatusIn(BaseModel):
    status: str
    proof_ref: str | None = None


def _conn():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c


def _driver(passcode: str) -> Dict[str, Any]:
    if not passcode: raise HTTPException(401,'Driver passcode required')
    c=_conn()
    try: row=c.execute('SELECT * FROM drivers WHERE passcode=? AND is_active=1',(passcode,)).fetchone()
    finally: c.close()
    if not row: raise HTTPException(401,'Invalid driver passcode')
    return dict(row)


def _ensure(c):
    c.execute('''CREATE TABLE IF NOT EXISTS ugatu_driver_shifts(
      id TEXT PRIMARY KEY, driver_id TEXT NOT NULL, started_at REAL NOT NULL, ended_at REAL,
      status TEXT NOT NULL, start_odometer REAL, end_odometer REAL, reconciled_at REAL,
      notes TEXT, UNIQUE(driver_id,status))''')
    c.execute('''CREATE TABLE IF NOT EXISTS ugatu_shipment_legs(
      id TEXT PRIMARY KEY, shipment_id TEXT, task_id TEXT UNIQUE NOT NULL, driver_id TEXT NOT NULL,
      leg_type TEXT NOT NULL, status TEXT NOT NULL, from_location TEXT, to_location TEXT,
      started_at REAL, completed_at REAL, proof_ref TEXT, updated_at REAL NOT NULL)''')


def _materialize_legs(c, driver_id):
    tasks=c.execute('SELECT * FROM dispatch_tasks WHERE driver_id=? ORDER BY created_at',(driver_id,)).fetchall()
    now=time.time()
    for r in tasks:
        t=dict(r); task_id=str(t['id']); shipment=str(t.get('shipment_id') or t.get('shipment_number') or '')
        leg_type=str(t.get('task_type') or 'delivery').upper(); status=str(t.get('status') or 'assigned').lower()
        c.execute('''INSERT INTO ugatu_shipment_legs(id,shipment_id,task_id,driver_id,leg_type,status,from_location,to_location,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET shipment_id=excluded.shipment_id,leg_type=excluded.leg_type,status=excluded.status,to_location=excluded.to_location,updated_at=excluded.updated_at''',
          ('LEG-'+uuid.uuid4().hex[:12].upper(),shipment,task_id,driver_id,leg_type,status,None,t.get('location_text'),now))
    c.commit()

@router.post('/shift/start')
def start_shift(body:ShiftStartIn, x_driver_passcode:str=Header(default='')):
    d=_driver(x_driver_passcode); c=_conn()
    try:
        _ensure(c)
        existing=c.execute("SELECT * FROM ugatu_driver_shifts WHERE driver_id=? AND status='open'",(d['id'],)).fetchone()
        if existing: return dict(existing)
        row=c.execute('''INSERT INTO ugatu_driver_shifts(id,driver_id,started_at,status,start_odometer,notes)
          VALUES(?,?,?,?,?,?) RETURNING *''',('SHIFT-'+uuid.uuid4().hex[:12].upper(),d['id'],time.time(),'open',body.start_odometer,body.notes[:1000])).fetchone(); c.commit(); return dict(row)
    finally: c.close()

@router.get('/shift/current')
def current_shift(x_driver_passcode:str=Header(default='')):
    d=_driver(x_driver_passcode); c=_conn()
    try:
        _ensure(c); row=c.execute("SELECT * FROM ugatu_driver_shifts WHERE driver_id=? AND status='open' ORDER BY started_at DESC LIMIT 1",(d['id'],)).fetchone()
        return dict(row) if row else None
    finally: c.close()

@router.post('/shift/reconcile')
def reconcile_shift(body:ShiftReconcileIn, x_driver_passcode:str=Header(default='')):
    d=_driver(x_driver_passcode); c=_conn()
    try:
        _ensure(c); _materialize_legs(c,d['id'])
        active=c.execute("SELECT COUNT(*) n FROM dispatch_tasks WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')",(d['id'],)).fetchone()['n']
        open_legs=c.execute("SELECT COUNT(*) n FROM ugatu_shipment_legs WHERE driver_id=? AND status NOT IN ('completed','failed','cancelled','dropped_off_customer','dropped_off_warehouse')",(d['id'],)).fetchone()['n']
        if active or open_legs: raise HTTPException(409,f'Shift cannot reconcile with {active} active task(s) and {open_legs} open leg(s)')
        row=c.execute("SELECT * FROM ugatu_driver_shifts WHERE driver_id=? AND status='open' ORDER BY started_at DESC LIMIT 1",(d['id'],)).fetchone()
        if not row: raise HTTPException(409,'No open shift')
        now=time.time(); out=c.execute("UPDATE ugatu_driver_shifts SET status='reconciled',ended_at=?,reconciled_at=?,end_odometer=?,notes=? WHERE id=? RETURNING *",(now,now,body.end_odometer,body.notes[:1000],row['id'])).fetchone(); c.commit(); return dict(out)
    finally: c.close()

@router.get('/legs')
def legs(x_driver_passcode:str=Header(default='')):
    d=_driver(x_driver_passcode); c=_conn()
    try:
        _ensure(c); _materialize_legs(c,d['id']); rows=c.execute('SELECT * FROM ugatu_shipment_legs WHERE driver_id=? ORDER BY updated_at DESC',(d['id'],)).fetchall(); return {'count':len(rows),'results':[dict(x) for x in rows]}
    finally: c.close()

@router.post('/legs/{leg_id}/status')
def leg_status(leg_id:str, body:LegStatusIn, x_driver_passcode:str=Header(default='')):
    d=_driver(x_driver_passcode); status=body.status.strip().lower(); c=_conn()
    try:
        _ensure(c); row=c.execute('SELECT * FROM ugatu_shipment_legs WHERE id=? AND driver_id=?',(leg_id,d['id'])).fetchone()
        if not row: raise HTTPException(404,'Shipment leg not found')
        now=time.time(); started=row['started_at'] or (now if status not in {'assigned','queued'} else None); completed=now if status in FINAL else None
        out=c.execute('UPDATE ugatu_shipment_legs SET status=?,started_at=?,completed_at=?,proof_ref=?,updated_at=? WHERE id=? RETURNING *',(status,started,completed,body.proof_ref,now,leg_id)).fetchone(); c.commit(); return dict(out)
    finally: c.close()

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
HR_DIR = BASE_DIR / "ugaforce_hr"
DASHBOARD = HR_DIR / "dashboard.html"
DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")

app = FastAPI(
    title="UGAFORCE-HR",
    version="1.0.0-alpha.1",
    description="Independent corporate HR management system for the Uganda National Grid ecosystem.",
)

origins = [x.strip() for x in os.getenv("UGAFORCE_HR_ALLOWED_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False if origins == ["*"] else True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
)


def _db_status() -> dict[str, Any]:
    if not DATABASE_URL:
        return {"configured": False, "connected": False, "detail": "UGAFORCE_HR_DATABASE_URL is not set"}
    try:
        with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select current_database(), current_user, version()")
                database, user, version = cur.fetchone()
                cur.execute("select to_regclass('public.ugaforce_hr_employees') is not null")
                schema_ready = bool(cur.fetchone()[0])
        return {
            "configured": True,
            "connected": True,
            "database": database,
            "user": user,
            "schema_ready": schema_ready,
            "engine": version.split(',')[0],
        }
    except Exception as exc:
        return {"configured": True, "connected": False, "detail": str(exc)[:240]}


@app.get("/health")
def health() -> dict[str, Any]:
    db = _db_status()
    return {
        "status": "ok" if db.get("connected") else "degraded",
        "service": "UGAFORCE-HR",
        "version": app.version,
        "database": db,
    }


@app.get("/api/v1/system/status")
def system_status() -> dict[str, Any]:
    return health()


@app.get("/api/v1/departments")
def departments() -> dict[str, Any]:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    try:
        with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select id::text, name, parent_dept_id::text, created_at from ugaforce_hr_departments order by name")
                rows = cur.fetchall()
        return {"results": [dict(zip(("id", "name", "parent_dept_id", "created_at"), row)) for row in rows]}
    except psycopg2.errors.UndefinedTable:
        raise HTTPException(status_code=503, detail="UGAFORCE-HR schema has not been migrated yet")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(exc)[:180]}")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD, media_type="text/html", headers={"Cache-Control": "no-store"})

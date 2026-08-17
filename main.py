import os

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Uganda National Grid API",
    version="2.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL missing")

    return psycopg.connect(DATABASE_URL)


def format_record(row):
    return {
        "id": row[0],
        "grid_id": row[1],
        "country": row[2],
        "district_code": row[3],
        "subcounty_code": row[4],
        "parish_code": row[5],
        "building_id": row[6],
        "latitude": row[7],
        "longitude": row[8],
        "address": row[9]
    }


@app.get("/")
def root():
    return {
        "service": "Uganda National Grid API",
        "status": "online",
        "version": "2.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/search")
def search(q: str):

    if not q:
        raise HTTPException(
            status_code=400,
            detail="Search text required"
        )

    pattern = f"%{q}%"

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                FROM uganda_grid_records
                WHERE
                    grid_id ILIKE %s
                    OR building_id ILIKE %s
                    OR address ILIKE %s
                LIMIT 25;
                """,
                (
                    pattern,
                    pattern,
                    pattern
                )
            )

            rows = cur.fetchall()

    return [
        format_record(row)
        for row in rows
    ]


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                FROM uganda_grid_records
                WHERE grid_id = %s
                LIMIT 1;
                """,
                (grid_id,)
            )

            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    return format_record(row)


@app.get("/building/{building_id}")
def get_building(building_id: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                FROM uganda_grid_records
                WHERE building_id = %s
                LIMIT 1;
                """,
                (building_id,)
            )

            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Building not found"
        )

    return format_record(row)

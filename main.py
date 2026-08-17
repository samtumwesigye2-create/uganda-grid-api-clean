import os
import re

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(
    title="Uganda National Grid API",
    version="3.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.environ.get("DATABASE_URL")


class GridRecordCreate(BaseModel):
    grid_id: str
    country: str = "UG"
    district_code: str
    subcounty_code: str
    parish_code: str
    building_id: str
    latitude: float
    longitude: float
    address: str | None = None


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")

    return psycopg.connect(DATABASE_URL)


def create_tables():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uganda_grid_records (
                    id BIGSERIAL PRIMARY KEY,
                    grid_id TEXT NOT NULL,
                    country TEXT NOT NULL,
                    district_code TEXT NOT NULL,
                    subcounty_code TEXT NOT NULL,
                    parish_code TEXT NOT NULL,
                    building_id TEXT NOT NULL,
                    latitude DOUBLE PRECISION NOT NULL,
                    longitude DOUBLE PRECISION NOT NULL,
                    address TEXT
                );
                """
            )

        conn.commit()


def row_to_record(row):
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
        "address": row[9],
    }


@app.on_event("startup")
def startup_event():
    create_tables()


@app.get("/")
def root():
    return {
        "name": "Uganda National Grid API",
        "version": "3.0",
        "status": "online",
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/db-health")
def db_health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()

        return {
            "status": "ok",
            "database": "connected"
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {exc}"
        )


@app.post("/grid-record")
def create_grid_record(record: GridRecordCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO uganda_grid_records (
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address;
                """,
                (
                    record.grid_id,
                    record.country,
                    record.district_code,
                    record.subcounty_code,
                    record.parish_code,
                    record.building_id,
                    record.latitude,
                    record.longitude,
                    record.address,
                )
            )

            row = cur.fetchone()

        conn.commit()

    return row_to_record(row)


@app.get("/grid-records")
def get_grid_records(limit: int = 100):
    if limit < 1:
        limit = 1

    if limit > 1000:
        limit = 1000

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
                ORDER BY id
                LIMIT %s;
                """,
                (limit,)
            )

            rows = cur.fetchall()

    return [
        row_to_record(row)
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
            detail="Grid location not found"
        )

    return row_to_record(row)


@app.get("/search")
def search_address(q: str):
    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query is required"
        )

    full_pattern = f"%{query}%"

    # Break a normal address into words.
    # Example:
    # "1001 Victoria Drive"
    # becomes:
    # ["1001", "Victoria", "Drive"]
    #
    # This lets it match:
    # "1001 Lake Victoria Drive, Lake Victoria, Entebbe..."
    tokens = re.findall(
        r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*",
        query
    )

    if not tokens:
        tokens = [query]

    token_conditions = " AND ".join(
        ["address ILIKE %s"] * len(tokens)
    )

    token_values = [
        f"%{token}%"
        for token in tokens
    ]

    sql = f"""
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
            OR (
                {token_conditions}
            )
        ORDER BY
            CASE
                WHEN grid_id ILIKE %s THEN 0
                WHEN building_id ILIKE %s THEN 1
                WHEN address ILIKE %s THEN 2
                ELSE 3
            END,
            id
        LIMIT 25;
    """

    parameters = (
        [
            full_pattern,
            full_pattern,
            full_pattern,
        ]
        + token_values
        + [
            full_pattern,
            full_pattern,
            full_pattern,
        ]
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                parameters
            )

            rows = cur.fetchall()

    return [
        row_to_record(row)
        for row in rows
    ]

import os

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uganda_grid_records (
                    id BIGSERIAL PRIMARY KEY,

                    grid_id TEXT UNIQUE NOT NULL,

                    country TEXT NOT NULL DEFAULT 'UG',

                    district_code TEXT NOT NULL,

                    subcounty_code TEXT NOT NULL,

                    parish_code TEXT NOT NULL,

                    building_id TEXT NOT NULL,

                    latitude DOUBLE PRECISION NOT NULL,

                    longitude DOUBLE PRECISION NOT NULL,

                    address TEXT,

                    created_at TIMESTAMPTZ
                    DEFAULT CURRENT_TIMESTAMP
                );
            """)

        conn.commit()


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/")
def root():
    return {
        "service": "Uganda National Grid API",
        "status": "online",
        "phase": 3
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/db-health")
def db_health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "test": result[0]
        }

    except Exception as e:
        return {
            "status": "error",
            "database": "connection failed",
            "message": str(e)
        }


@app.post("/grid-record")
def create_grid_record(record: GridRecordCreate):

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute("""
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
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
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
                """, (
                    record.grid_id,
                    record.country,
                    record.district_code,
                    record.subcounty_code,
                    record.parish_code,
                    record.building_id,
                    record.latitude,
                    record.longitude,
                    record.address
                ))

                row = cur.fetchone()

            conn.commit()

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

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="This grid_id already exists"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/grid-records")
def get_grid_records(limit: int = 100):

    limit = max(1, min(limit, 1000))

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
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
            """, (limit,))

            rows = cur.fetchall()

    return [
        {
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

        for row in rows
    ]


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
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

                WHERE grid_id = %s;
            """, (grid_id,))

            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Grid location not found"
        )

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

@app.get("/search")
def search_address(q: str):
    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query is required"
        )

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
                    OR address ILIKE %s
                    OR building_id ILIKE %s
                ORDER BY id
                LIMIT 25;
                """,
                (
                    f"%{query}%",
                    f"%{query}%",
                    f"%{query}%"
                )
            )

            rows = cur.fetchall()

    return [
        {
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
        for row in rows
    ]

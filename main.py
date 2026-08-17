import os
import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row

app = FastAPI(
    title="Uganda National Grid API",
    version="2.0.0"
)

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL missing")
    
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS uganda_grid_records (
        id SERIAL PRIMARY KEY,
        grid_id TEXT UNIQUE,
        building_id TEXT,
        address TEXT,
        street TEXT,
        house_number TEXT,
        district TEXT,
        sub_county TEXT,
        parish TEXT,
        zip_code TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    create_tables()


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

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM uganda_grid_records
        WHERE
            address ILIKE %s
            OR street ILIKE %s
            OR building_id ILIKE %s
            OR grid_id ILIKE %s
        LIMIT 50;
    """,
    (
        f"%{q}%",
        f"%{q}%",
        f"%{q}%",
        f"%{q}%"
    ))

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM uganda_grid_records
        WHERE grid_id=%s;
    """,
    (grid_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    return result


@app.get("/building/{building_id}")
def get_building(building_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM uganda_grid_records
        WHERE building_id=%s;
    """,
    (building_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Building not found"
        )

    return result

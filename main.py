from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, UploadFile, File, Query
import json
import os
import psycopg2

app = FastAPI(
    title="Uganda National Grid API",
    version="2.0.0"
)


def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )


def setup_database():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS uganda_grid_records (
        id SERIAL PRIMARY KEY,
        grid_id TEXT UNIQUE,
        building_id TEXT,
        address TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        zip_code TEXT,
        division TEXT,
        house_number TEXT,
        street TEXT,
        city TEXT,
        region TEXT
    );
    """)

    columns = {
        "grid_id": "TEXT",
        "building_id": "TEXT",
        "address": "TEXT",
        "latitude": "DOUBLE PRECISION",
        "longitude": "DOUBLE PRECISION",
        "zip_code": "TEXT",
        "division": "TEXT",
        "house_number": "TEXT",
        "street": "TEXT",
        "city": "TEXT",
        "region": "TEXT"
    }

    for column, datatype in columns.items():
        cur.execute(
            f"""
            ALTER TABLE uganda_grid_records
            ADD COLUMN IF NOT EXISTS {column} {datatype};
            """
        )

    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    setup_database()


@app.get("/")
def root():
    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "version": "2.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/import")
async def import_records(file: UploadFile = File(...)):

    data = await file.read()

    records = json.loads(data)

    conn = get_connection()
    cur = conn.cursor()

    count = 0

    for r in records:

        cur.execute("""
        INSERT INTO uganda_grid_records
        (
            grid_id,
            building_id,
            address,
            latitude,
            longitude,
            zip_code,
            division,
            house_number,
            street,
            city,
            region
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (grid_id)
        DO UPDATE SET
            building_id=EXCLUDED.building_id,
            address=EXCLUDED.address,
            latitude=EXCLUDED.latitude,
            longitude=EXCLUDED.longitude,
            zip_code=EXCLUDED.zip_code,
            division=EXCLUDED.division,
            house_number=EXCLUDED.house_number,
            street=EXCLUDED.street,
            city=EXCLUDED.city,
            region=EXCLUDED.region;
        """,
        (
            r.get("grid_id"),
            r.get("building_id"),
            r.get("address"),
            r.get("latitude"),
            r.get("longitude"),
            r.get("zip_code"),
            r.get("division"),
            r.get("house_number"),
            r.get("street"),
            r.get("city"),
            r.get("region")
        ))

        count += 1


    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Import complete",
        "records_added": count
    }


@app.get("/search")
def search(q: str = Query(...)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM uganda_grid_records
    WHERE
    address ILIKE %s
    OR building_id ILIKE %s
    OR street ILIKE %s
    OR city ILIKE %s
    LIMIT 100;
    """,
    (
        f"%{q}%",
        f"%{q}%",
        f"%{q}%",
        f"%{q}%"
    ))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM uganda_grid_records
    WHERE grid_id=%s;
    """,(grid_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result or {}


@app.get("/building/{building_id}")
def get_building(building_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT *
    FROM uganda_grid_records
    WHERE building_id=%s;
    """,(building_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result or {}

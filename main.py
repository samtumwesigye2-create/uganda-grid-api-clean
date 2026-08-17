from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg
import json
import os

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
    return psycopg.connect(DATABASE_URL)


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


@app.post("/import")
async def import_records(file: UploadFile = File(...)):

    data = await file.read()

    records = json.loads(data)

    conn = get_connection()
    cur = conn.cursor()

    count = 0

    for r in records:

        cur.execute(
            """
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
                %(grid_id)s,
                %(building_id)s,
                %(address)s,
                %(latitude)s,
                %(longitude)s,
                %(zip_code)s,
                %(division)s,
                %(house_number)s,
                %(street)s,
                %(city)s,
                %(region)s
            )
            ON CONFLICT (building_id)
            DO NOTHING
            """,
            r
        )

        count += 1


    conn.commit()
    cur.close()
    conn.close()


    return {
        "status": "success",
        "imported": count
    }



@app.get("/search")
def search(q: str = Query(...)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE
        address ILIKE %s
        OR building_id ILIKE %s
        OR grid_id ILIKE %s
        LIMIT 50
        """,
        (
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        )
    )

    rows = cur.fetchall()

    columns = [
        desc[0]
        for desc in cur.description
    ]

    cur.close()
    conn.close()


    return [
        dict(zip(columns,row))
        for row in rows
    ]



@app.get("/address/{grid_id}")
def get_address(grid_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE grid_id=%s
        """,
        (grid_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row



@app.get("/building/{building_id}")
def get_building(building_id: str):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE building_id=%s
        """,
        (building_id,)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row

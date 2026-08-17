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


@app.get("/")
def root():
    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "version": "2.0.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/search")
def search(q: str = Query(...)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE address ILIKE %s
        OR city ILIKE %s
        OR building_id ILIKE %s
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
        "grid_id",
        "building_id",
        "address",
        "latitude",
        "longitude",
        "zip_code",
        "division",
        "house_number",
        "street",
        "city",
        "region"
    ]

    result = []

    for row in rows:
        result.append(
            dict(zip(columns, row))
        )

    cur.close()
    conn.close()

    return result


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

    if row:
        return row

    return {
        "error": "Address not found"
    }


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

    if row:
        return row

    return {
        "error": "Building not found"
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
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
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
            )
        )

        count += 1


    conn.commit()

    cur.close()
    conn.close()


    return {
        "message": "Import successful",
        "records_added": count
    }

from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import json
import os
import psycopg2


app = FastAPI(
    title="Uganda National Grid API",
    version="2.0"
)


# Serve website files
app.mount(
    "/static",
    StaticFiles(directory="."),
    name="static"
)


def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )



@app.get("/")
def home():
    return FileResponse("index.html")



@app.get("/health")
def health():

    return {
        "status": "healthy"
    }



@app.get("/api")
def api_info():

    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "version": "2.0"
    }



@app.post("/import")
async def import_records(
    file: UploadFile = File(...)
):

    contents = await file.read()

    records = json.loads(contents)


    conn = get_connection()
    cur = conn.cursor()


    count = 0


    for r in records:

        cur.execute(
            """
            INSERT INTO uganda_grid_records
            (
            id,
            grid_id,
            building_id,
            address,
            street,
            house_number,
            zip_code,
            latitude,
            longitude,
            area,
            city,
            region
            )

            VALUES
            (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,

            (
            r.get("id"),
            r.get("grid_id"),
            r.get("building_id"),
            r.get("address"),
            r.get("street"),
            r.get("house_number"),
            r.get("zip_code"),
            r.get("latitude"),
            r.get("longitude"),
            r.get("area"),
            r.get("city"),
            r.get("region")
            )
        )

        count += 1


    conn.commit()

    cur.close()
    conn.close()


    return {
        "message":"Import complete",
        "records_added":count
    }




@app.get("/search")
def search(
    q: str = Query(...)
):

    conn = get_connection()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE
        address ILIKE %s
        OR street ILIKE %s
        OR city ILIKE %s
        OR grid_id ILIKE %s

        LIMIT 100
        """,

        (
        f"%{q}%",
        f"%{q}%",
        f"%{q}%",
        f"%{q}%"
        )
    )


    results = cur.fetchall()


    cur.close()
    conn.close()


    return results
            

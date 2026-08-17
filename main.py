from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import psycopg2


app = FastAPI(
    title="Uganda National Grid API",
    version="2.0"
)


# Serve frontend files
app.mount(
    "/static",
    StaticFiles(directory="frontend"),
    name="static"
)


# Website homepage
@app.get("/")
def homepage():
    return FileResponse(
        "frontend/index.html"
    )


# Database connection
def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )


# API status
@app.get("/api")
def api_status():
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


# Search database
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

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

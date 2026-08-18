from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import psycopg2
import os


app = FastAPI(
    title="Uganda National Grid API",
    version="2.0"
)


# Database connection
def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )


# Serve frontend files if they exist
if os.path.exists("frontend"):
    app.mount(
        "/static",
        StaticFiles(directory="frontend"),
        name="static"
    )


# Homepage
@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")

    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")

    return {
        "message": "Frontend file missing"
    }


# Health check
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# API information
@app.get("/api")
def api_info():
    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "version": "2.0"
    }


# Search records
@app.get("/search")
def search(
    q: str = Query("")
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM uganda_grid_records
        WHERE
        address ILIKE %s
        OR code ILIKE %s
        LIMIT 100
        """,
        (
            f"%{q}%",
            f"%{q}%"
        )
    )


    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

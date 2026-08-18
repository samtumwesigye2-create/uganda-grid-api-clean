from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import os
import psycopg2

app = FastAPI(
    title="Uganda National Grid API",
    version="2.0"
)


def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )


@app.get("/")
def home():
    return {
        "message": "Uganda National Grid API is running"
    }


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
        OR street ILIKE %s
        OR city ILIKE %s
        LIMIT 100
        """,
        (
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        )
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

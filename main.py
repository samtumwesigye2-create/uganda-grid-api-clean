from fastapi import FastAPI, Query
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


# Homepage
@app.get("/")
def home():
    return {
        "message": "Uganda National Grid API is running",
        "status": "online",
        "version": "2.0"
    }


# Health check
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# API info
@app.get("/api")
def api_info():
    return {
        "name": "Uganda National Grid API",
        "status": "online",
        "version": "2.0"
    }


# Search grid records
@app.get("/search")
def search(q: str = Query("")):

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
            "%" + q + "%",
            "%" + q + "%"
        )
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

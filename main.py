from fastapi import FastAPI

app = FastAPI(title="Uganda National Grid API")


@app.get("/")
def root():
    return {
        "service": "Uganda National Grid API",
        "status": "online",
        "phase": 2
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/grid")
def grid():
    return {
        "country": "UG",
        "system": "Uganda National Grid",
        "status": "ready"
    }


@app.get("/address/{grid_id}")
def address(grid_id: str):
    return {
        "grid_id": grid_id,
        "country": "UG",
        "district": "Sample District",
        "subcounty": "Sample Subcounty",
        "parish": "Sample Parish",
        "building_id": "000245",
        "coordinates": {
            "latitude": 0.0,
            "longitude": 32.0
        }
    }
TEST_RECORDS = [
    {
        "grid_id": "UG-101-045-018-000245",
        "country": "UG",
        "district": "Test District",
        "subcounty": "Test Subcounty",
        "parish": "Test Parish",
        "building_id": "000245",
        "latitude": 0.0,
        "longitude": 32.0
    },
    {
        "grid_id": "UG-101-045-018-000246",
        "country": "UG",
        "district": "Test District",
        "subcounty": "Test Subcounty",
        "parish": "Test Parish",
        "building_id": "000246",
        "latitude": 0.001,
        "longitude": 32.001
    }
]


@app.get("/records")
def records():
    return TEST_RECORDS
import os
import psycopg

@app.get("/db-health")
def db_health():
    try:
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            return {
                "status": "error",
                "database": "not connected",
                "message": "DATABASE_URL is missing"
            }

        with psycopg.connect(database_url) as conn:
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
            "message": str(e)
        }

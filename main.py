from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json


app = FastAPI(
    title="Uganda National Grid API",
    version="2.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "entebbe_database.json"
INDEX_FILE = BASE_DIR / "index.html"


# Load data
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
else:
    records = []


# THIS IS THE WEBSITE PAGE
@app.get("/")
def home():

    if INDEX_FILE.exists():
        return FileResponse(
            INDEX_FILE
        )

    return JSONResponse(
        {
            "error": "index.html not found",
            "location": str(INDEX_FILE)
        }
    )


# API status
@app.get("/api")
def api():

    return {
        "message": "Uganda National Grid API is running",
        "records": len(records)
    }


# Health check
@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# Search
@app.get("/search")
def search(
    q: str = Query(...)
):

    query = q.lower()

    results = []

    for item in records:

        text = json.dumps(item).lower()

        if query in text:
            results.append(item)


    return {
        "count": len(results),
        "results": results
    }

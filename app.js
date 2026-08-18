from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import json
import os

app = FastAPI(
    title="Uganda National Grid API"
)

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load database
DATA_FILE = "entebbe_database.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        database = json.load(f)
else:
    database = []


# Frontend homepage
@app.get("/")
def home():
    if os.path.exists("index.html"):
        return FileResponse("index.html")

    return JSONResponse(
        {
            "message": "Frontend file missing",
            "checked": [
                "/app/index.html",
                "/app/frontend/index.html",
                "/app/static/index.html"
            ]
        }
    )


# API status
@app.get("/api")
def api_status():
    return {
        "message": "Uganda National Grid API is running"
    }


# Search endpoint
@app.get("/search")
def search(q: str = Query(...)):

    q = q.lower()

    results = []

    for item in database:

        text = json.dumps(item).lower()

        if q in text:
            results.append(item)


    return {
        "count": len(results),
        "results": results
    }


# Get all records
@app.get("/records")
def records():
    return {
        "count": len(database),
        "results": database
    }

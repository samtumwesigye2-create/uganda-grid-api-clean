from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json
import os

app = FastAPI(title="Uganda National Grid API")

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent

# Database file
DATABASE_FILE = BASE_DIR / "entebbe_database.json"


@app.get("/")
def home():
    return {
        "message": "Uganda National Grid API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/search")
def search(q: str = Query(...)):
    if not DATABASE_FILE.exists():
        return JSONResponse(
            status_code=500,
            content={
                "error": "Database file missing",
                "file": str(DATABASE_FILE)
            }
        )

    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    results = []

    query = q.lower()

    for item in data:

        item_text = json.dumps(item).lower()

        if query in item_text:

            results.append({
                "id": item.get("id"),
                "code": item.get("code"),
                "address": item.get("address"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude")
            })


    return {
        "count": len(results),
        "results": results
    }


# Serve frontend
@app.get("/app")
def frontend():
    frontend_file = BASE_DIR / "index.html"

    if frontend_file.exists():
        return FileResponse(frontend_file)

    return {
        "message": "Frontend file missing",
        "checked": [
            str(BASE_DIR / "index.html"),
            str(BASE_DIR / "frontend" / "index.html")
        ]
    }


@app.get("/debug/files")
def debug_files():
    return {
        "files": os.listdir(BASE_DIR)
    }

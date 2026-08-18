from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import json
import os


app = FastAPI(title="Uganda National Grid API")


# Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
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
        return {
            "error": "Database file missing",
            "checked": str(DATABASE_FILE)
        }


    with open(
        DATABASE_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)


    results = []

    query = q.lower()


    for item in data:

        text = json.dumps(item).lower()

        if query in text:
            results.append(item)


    return {
        "count": len(results),
        "results": results
    }



# Frontend
@app.get("/app")
def frontend():

    index = BASE_DIR / "index.html"

    if index.exists():
        return FileResponse(index)

    return {
        "message": "Frontend file missing",
        "checked": [
            str(BASE_DIR / "index.html"),
            str(BASE_DIR / "frontend" / "index.html")
        ]
    }



@app.get("/debug/files")
def files():

    return {
        "files": os.listdir(BASE_DIR)
    }

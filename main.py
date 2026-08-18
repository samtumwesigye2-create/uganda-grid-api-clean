from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="Uganda National Grid API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


@app.get("/")
def home():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return {"message": "Frontend file missing"}


@app.get("/api")
def api():
    return {
        "message": "Uganda National Grid API is running"
    }

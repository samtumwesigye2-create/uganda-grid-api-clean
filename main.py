from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

app = FastAPI(title="Uganda National Grid API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

POSSIBLE_FILES = [
    BASE_DIR / "index.html",
    BASE_DIR / "frontend" / "index.html",
    BASE_DIR / "static" / "index.html",
    Path("/app/index.html"),
]


@app.get("/")
def home():
    for file in POSSIBLE_FILES:
        if file.exists():
            return FileResponse(file)

    return JSONResponse(
        {
            "message": "Frontend file missing",
            "checked": [str(x) for x in POSSIBLE_FILES]
        },
        status_code=404
    )


@app.get("/api")
def api():
    return {
        "message": "Uganda National Grid API is running"
    }

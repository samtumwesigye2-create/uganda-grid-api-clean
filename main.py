import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Uganda National Grid API")

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@@app.get("/")
def home():
    return FileResponse("index.html")

    return {
        "message": "Uganda National Grid API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

app = FastAPI(title="Uganda National Grid API")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Serve frontend if it exists
if FRONTEND_DIR.exists():
    app.mount(
        "/frontend",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="frontend"
    )


@app.get("/")
def home():
    index = FRONTEND_DIR / "index.html"

    if index.exists():
        return FileResponse(str(index))

    return JSONResponse(
        {"message": "Uganda National Grid API is running"}
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# Railway startup
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )

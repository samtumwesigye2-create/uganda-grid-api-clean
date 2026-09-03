from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ugatu.ugatu_routes import router as ugatu_router

app = FastAPI(title="UGATU Command Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(ugatu_router)


@app.get("/")
def root():
    return {
        "service": "UGATU — Uganda National Grid Transaction U-Codes",
        "version": "1.0.0",
        "health": "/api/ugatu/health",
        "docs": "/docs",
    }

"""Application entrypoint that extends the existing FastAPI app."""

from main import app
from national_zip_api import router as national_zip_router

app.include_router(national_zip_router)

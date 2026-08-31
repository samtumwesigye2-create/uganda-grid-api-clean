"""Production entrypoint with UGAMAP Core + persistent user accounts."""

from ugamap_entrypoint import app
from ugamap_accounts import router as ugamap_accounts_router

app.include_router(ugamap_accounts_router)

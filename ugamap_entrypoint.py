"""Production entrypoint with UGAMAP Core enabled.

This wrapper leaves the existing entrypoint untouched, then attaches the
shared UGAMAP Core router to the already-configured FastAPI application.
"""

from entrypoint import app
from main import REPORTS, addresses, prune_reports
from postal_assignment import resolve_zip
from state_geometry import state_for_coordinate
from ugamap_core import configure_core, router as ugamap_core_router


def _core_reports_source():
    prune_reports()
    return REPORTS


configure_core(
    address_source=lambda: addresses,
    state_lookup=state_for_coordinate,
    zip_lookup=resolve_zip,
    reports_source=_core_reports_source,
)

app.include_router(ugamap_core_router)

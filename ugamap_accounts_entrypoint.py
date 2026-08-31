"""Production entrypoint with UGAMAP Core + persistent user accounts."""

from pathlib import Path
from fastapi.responses import Response

from ugamap_entrypoint import app
from ugamap_accounts import router as ugamap_accounts_router

app.include_router(ugamap_accounts_router)

# Replace the public home route with the same working UGAMAP page plus account UI.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
        app.router.routes.remove(route)


@app.get("/", include_in_schema=False)
def ugamap_home_with_accounts():
    source = Path("index.html").read_text(encoding="utf-8")
    if "/boundaries.js" not in source:
        leaflet = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        source = source.replace(leaflet, leaflet + '\n<script src="/boundaries.js?v=3"></script>', 1)
    account_script = '<script src="/assets/ugamap-account-ui.js?v=1"></script>'
    if account_script not in source:
        source = source.replace("</body>", account_script + "\n</body>") if "</body>" in source else source + account_script
    return Response(source, media_type="text/html", headers={"Cache-Control":"no-cache, no-store, must-revalidate"})

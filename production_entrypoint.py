"""Production wrapper that prevents duplicate UGAMAP boundary initialization."""

from fastapi.responses import Response

from entrypoint import app
from main import APP_JS_FILE


# index.html now loads /boundaries.js explicitly before /app.js.
# Remove the older /app.js handler that prepended boundaries.js a second time.
for route in list(app.router.routes):
    if getattr(route, "path", None) == "/app.js" and "GET" in getattr(route, "methods", set()):
        app.router.routes.remove(route)


@app.get("/app.js", include_in_schema=False)
def app_js_once():
    with open(APP_JS_FILE, "r", encoding="utf-8") as handle:
        code = handle.read()
    return Response(
        content=code,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )

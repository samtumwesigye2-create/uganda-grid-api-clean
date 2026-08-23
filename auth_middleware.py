"""
Passcode protection middleware.

Drop this file in your repo root (next to main.py), then wire it in
as shown at the bottom of this file. It checks every incoming request
for a secret passcode before your route functions ever run.
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

PASSCODE = os.environ.get("PASSCODE")

OPEN_PATHS = {"/health", "/"}


class PasscodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in OPEN_PATHS:
            return await call_next(request)

        if not PASSCODE:
            return JSONResponse(
                {"error": "Server misconfigured: no passcode set"}, status_code=503
            )

        supplied = request.headers.get("x-passcode") or request.query_params.get("passcode")

        if supplied != PASSCODE:
            return JSONResponse({"error": "Invalid or missing passcode"}, status_code=401)

        return await call_next(request)


# In main.py:
# from auth_middleware import PasscodeMiddleware
# app.add_middleware(PasscodeMiddleware)

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Reuses the same ADMIN_PASSCODE env var already used by /submissions
PASSCODE = os.environ.get("ADMIN_PASSCODE")

# Only these path prefixes require the passcode. Public/citizen-facing
# routes (/, /search, /address, /submit, /report, /auth/*, /news, etc.)
# stay open.
PROTECTED_PREFIXES = ("/admin", "/mailing", "/shipments")


class PasscodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        if not path.startswith(PROTECTED_PREFIXES):
            return await call_next(request)

        if not PASSCODE:
            return JSONResponse(
                {"error": "Server misconfigured: no passcode set"}, status_code=503
            )

        supplied = request.headers.get("x-passcode") or request.query_params.get("passcode")

        if supplied != PASSCODE:
            return JSONResponse({"error": "Invalid or missing passcode"}, status_code=401)

        return await call_next(request)

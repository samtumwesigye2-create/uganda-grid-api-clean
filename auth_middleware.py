import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Reuses the same ADMIN_PASSCODE env var already used by /submissions
PASSCODE = os.environ.get("ADMIN_PASSCODE")

# NOTE: /admin is intentionally NOT protected here. Browsers can't send
# custom headers on a plain page navigation, so gating /admin itself
# would block the page before its own built-in login screen could ever
# load. admin.html already gates its real content (and its API calls)
# behind that login screen, using the same ADMIN_PASSCODE via the
# X-Admin-Passcode header — matching check_admin() in main.py.
#
# Add path prefixes here only for routes that are pure APIs (never
# loaded directly by browser navigation) and that don't already have
# their own passcode check.
PROTECTED_PREFIXES = ()


class PasscodeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        if not PROTECTED_PREFIXES or not path.startswith(PROTECTED_PREFIXES):
            return await call_next(request)

        if not PASSCODE:
            return JSONResponse(
                {"error": "Server misconfigured: no passcode set"}, status_code=503
            )

        supplied = request.headers.get("x-passcode") or request.query_params.get("passcode")

        if supplied != PASSCODE:
            return JSONResponse({"error": "Invalid or missing passcode"}, status_code=401)

        return await call_next(request)

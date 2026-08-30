"""
internal_api.py
Drop into BOTH backends. Separate from user login — this is how
the two servers trust each other's direct API calls.

Set on BOTH deployments (same value):
    INTERNAL_API_KEY=<random string>
Generate with: python -c "import secrets; print(secrets.token_hex(32))"
"""

import os
import hmac
from fastapi import HTTPException, Header

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
if not INTERNAL_API_KEY:
    raise RuntimeError("INTERNAL_API_KEY env var is not set")


def require_internal_key(x_internal_key: str = Header(default=None)) -> None:
    if not x_internal_key or not hmac.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing internal key")


# Example of how one app calls the other:
#
# import requests
# def call_ugamap_verify_address(lat, lng):
#     resp = requests.post(
#         "https://maps.ugandagrid.com/internal/verify-address",
#         json={"lat": lat, "lng": lng},
#         headers={"X-Internal-Key": INTERNAL_API_KEY},
#         timeout=10,
#     )
#     resp.raise_for_status()
#     return resp.json()

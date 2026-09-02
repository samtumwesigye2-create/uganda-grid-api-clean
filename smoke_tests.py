"""UGAMAP integration smoke tests.

Runs without pytest/httpx. It imports the real FastAPI app, exercises it through
ASGI, verifies every Extended Application route is registered, confirms the
static control pages are served, and checks authenticated read paths do not
raise 5xx errors.

Usage:
    ADMIN_PASSCODE=smoke-secret python smoke_tests.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from urllib.parse import urlsplit

# Set a deterministic test-only master code before importing the application.
os.environ.setdefault("ADMIN_PASSCODE", "ugamap-smoke-test-only")

from main import app  # noqa: E402

PASSCODE = os.environ["ADMIN_PASSCODE"]


async def asgi_request(method: str, path: str, headers: dict[str, str] | None = None, body: bytes = b""):
    parts = urlsplit(path)
    sent = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    raw_headers = [(k.lower().encode(), str(v).encode()) for k, v in (headers or {}).items()]
    if body and not any(k == b"content-length" for k, _ in raw_headers):
        raw_headers.append((b"content-length", str(len(body)).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": parts.path,
        "raw_path": parts.path.encode(),
        "query_string": parts.query.encode(),
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    await app(scope, receive, send)
    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    chunks = [m.get("body", b"") for m in sent if m["type"] == "http.response.body"]
    if start is None:
        raise AssertionError(f"No ASGI response for {method} {path}")
    return start["status"], b"".join(chunks)


def route_paths():
    return {getattr(r, "path", "") for r in app.routes}


def expect_route(paths: set[str], path: str):
    if path not in paths:
        raise AssertionError(f"Missing registered route: {path}")


async def main():
    failures = []
    checks = 0

    paths = route_paths()
    required_routes = [
        "/health",
        "/orders/summary",
        "/inventory/products",
        "/fleet/vehicles",
        "/yard/summary",
        "/analytics/summary",
        "/optimization/summary",
        "/digital-twin/snapshot",
        "/robotics/summary",
        "/visibility/summary",
        "/geography/zipper/status",
    ]
    for path in required_routes:
        checks += 1
        try:
            expect_route(paths, path)
            print(f"PASS route {path}")
        except Exception as exc:
            failures.append(str(exc)); print(f"FAIL route {path}: {exc}")

    pages = [
        "/assets/extended-applications.html",
        "/assets/platform-services.html",
        "/assets/transport-management.html",
        "/assets/order-management.html",
        "/assets/warehouse-control.html",
        "/assets/yard-management.html",
        "/assets/ai-ml-analytics.html",
        "/assets/optimization-engine.html",
        "/assets/digital-twin.html",
        "/assets/robotics-orchestration.html",
        "/assets/supply-chain-visibility.html",
    ]
    for page in pages:
        checks += 1
        try:
            status, content = await asgi_request("GET", page)
            if status != 200 or b"<html" not in content.lower():
                raise AssertionError(f"status={status}, html={b'<html' in content.lower()}")
            print(f"PASS page {page}")
        except Exception as exc:
            failures.append(f"{page}: {exc}"); print(f"FAIL page {page}: {exc}")

    checks += 1
    try:
        status, content = await asgi_request("GET", "/health")
        payload = json.loads(content or b"{}")
        if status != 200 or payload.get("status") != "ok":
            raise AssertionError(f"status={status}, payload={payload}")
        print("PASS API /health")
    except Exception as exc:
        failures.append(f"/health: {exc}"); print(f"FAIL API /health: {exc}")

    authenticated_reads = [
        "/orders/summary",
        "/inventory/products",
        "/fleet/vehicles",
        "/yard/summary",
        "/analytics/summary?window_days=14",
        "/optimization/summary",
        "/digital-twin/snapshot",
        "/robotics/summary",
        "/visibility/summary",
    ]
    auth_headers = {"x-access-code": PASSCODE}
    for endpoint in authenticated_reads:
        checks += 1
        try:
            status, content = await asgi_request("GET", endpoint, auth_headers)
            if status >= 500:
                raise AssertionError(f"server error {status}: {content[:500]!r}")
            if status not in (200, 204):
                raise AssertionError(f"unexpected status {status}: {content[:500]!r}")
            print(f"PASS API {endpoint}")
        except Exception as exc:
            failures.append(f"{endpoint}: {exc}"); print(f"FAIL API {endpoint}: {exc}")

    # Authentication regression: protected operations must reject an empty code,
    # rather than accidentally becoming public or crashing.
    protected = ["/analytics/summary", "/optimization/summary", "/robotics/summary", "/visibility/summary"]
    for endpoint in protected:
        checks += 1
        try:
            status, _ = await asgi_request("GET", endpoint)
            if status not in (401, 403):
                raise AssertionError(f"expected 401/403, got {status}")
            print(f"PASS auth {endpoint} -> {status}")
        except Exception as exc:
            failures.append(f"auth {endpoint}: {exc}"); print(f"FAIL auth {endpoint}: {exc}")

    print(f"\nUGAMAP smoke audit: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("Failures:")
        for failure in failures:
            print(" -", failure)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

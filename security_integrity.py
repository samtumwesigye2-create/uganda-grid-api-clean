"""Low-impact application integrity monitoring for production.

This module does not alter UGAMAP routing, ZIPPER, map rendering, or business
workflows. It provides an authenticated security status endpoint that checks
critical application files for unexpected disappearance, hash changes during
one process lifetime, and a small set of high-signal malicious-code markers.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from fastapi import APIRouter, Header

from auth import require_permission

router = APIRouter(prefix="/security/integrity", tags=["Security"])
ROOT = Path(__file__).resolve().parent

CRITICAL_FILES = (
    "production_safe_entrypoint.py",
    "ugamap_accounts_entrypoint.py",
    "ugamap_entrypoint.py",
    "entrypoint.py",
    "main.py",
    "security_layer.py",
    "index.html",
    "app.js",
    "app-core.js",
    "boundaries.js",
    "legacy-grid-killer.js",
)

# Keep signatures narrow to reduce false positives. These are indicators only;
# a hit is reported for review rather than automatically deleting anything.
SUSPICIOUS_MARKERS = (
    "curl http://",
    "wget http://",
    "nc -e ",
    "bash -i >& /dev/tcp/",
    "powershell -enc ",
    "frombase64string(",
    "eval(base64.b64decode(",
    "exec(base64.b64decode(",
    "os.system(request.",
    "subprocess.popen(request.",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in CRITICAL_FILES:
        path = ROOT / name
        result[name] = _sha256(path) if path.is_file() else None
    return result


BASELINE = _snapshot()
BASELINE_TIME = time.time()


def _scan_file(path: Path) -> list[str]:
    if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return []
    return [marker for marker in SUSPICIOUS_MARKERS if marker in text]


def integrity_report() -> dict:
    current = _snapshot()
    missing = [name for name, digest in current.items() if digest is None]
    changed = [
        name for name, digest in current.items()
        if BASELINE.get(name) is not None and digest is not None and digest != BASELINE.get(name)
    ]
    signatures = {}
    for name in CRITICAL_FILES:
        hits = _scan_file(ROOT / name)
        if hits:
            signatures[name] = hits

    # Runtime safety checks that do not modify application behavior.
    world_writable = []
    for name in CRITICAL_FILES:
        path = ROOT / name
        try:
            if path.is_file() and (path.stat().st_mode & 0o002):
                world_writable.append(name)
        except OSError:
            pass

    healthy = not missing and not changed and not signatures and not world_writable
    return {
        "status": "healthy" if healthy else "review_required",
        "healthy": healthy,
        "baseline_created_at": BASELINE_TIME,
        "checked_at": time.time(),
        "critical_files_checked": len(CRITICAL_FILES),
        "missing_files": missing,
        "runtime_hash_changes": changed,
        "suspicious_signature_hits": signatures,
        "world_writable_critical_files": world_writable,
        "scanner_mode": "read_only",
        "automatic_deletion": False,
        "note": "Signature hits are indicators for review, not proof of malware.",
    }


@router.get("/status")
def integrity_status(x_access_code: str = Header(default="")):
    require_permission(x_access_code, "inventory:read")
    return integrity_report()

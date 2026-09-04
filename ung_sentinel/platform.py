"""Compatibility facade for the UNG Sentinel platform.

Do not move the underlying modules until production consumers have migrated.
This facade lets new code use the Sentinel identity immediately while old
imports and routes continue to function.
"""

from security_layer import SecurityMiddleware, router as security_router
from security_integrity import router as integrity_router, integrity_report
from integration_gateway import router as integration_router

NAME = "UNG Sentinel"
COMPONENTS = {
    "security": security_router,
    "integrity": integrity_router,
    "integration": integration_router,
}

__all__ = [
    "NAME",
    "COMPONENTS",
    "SecurityMiddleware",
    "security_router",
    "integrity_router",
    "integration_router",
    "integrity_report",
]

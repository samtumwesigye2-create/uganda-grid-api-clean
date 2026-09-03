from __future__ import annotations

from typing import Any, Dict


def resolve_scan_ucode(context: Dict[str, Any]) -> str:
    """Resolve the driver's universal SCAN button to the correct numeric U-Code."""
    stop_type = str(context.get("stop_type") or "").upper()
    action = str(context.get("action") or "").upper()
    custody_action = str(context.get("custody_action") or "").upper()

    if stop_type == "PICKUP" or action == "PICKUP" or custody_action == "ACQUIRE":
        return "U-1550"
    if stop_type == "DELIVERY" or action == "DELIVERY" or custody_action == "RELEASE":
        return "U-1560"
    if stop_type in {"TRANSFER", "HANDOFF"} or action in {"TRANSFER", "HANDOFF"}:
        return "U-1570"
    if stop_type == "EXCEPTION" or action == "EXCEPTION":
        return "U-1580"
    return "U-1500"


def driver_home_actions(context: Dict[str, Any]) -> list[dict[str, str]]:
    scan_code = resolve_scan_ucode(context)
    return [
        {"label": "ROUTE", "ucode": "U-1800"},
        {"label": "ORDERS", "ucode": "U-5000"},
        {"label": "SCAN", "ucode": scan_code},
        {"label": "TASKS", "ucode": "U-2000"},
        {"label": "DOCUMENTS", "ucode": "U-1600"},
        {"label": "REPORT ISSUE", "ucode": "U-1310"},
    ]

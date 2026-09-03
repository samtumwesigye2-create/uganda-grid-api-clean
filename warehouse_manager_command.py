"""Manager-only command authorization and Vector 5250 command metadata."""
from fastapi import APIRouter, Header, HTTPException
from auth import require_permission, is_master

router = APIRouter(tags=["Warehouse Manager Command"])

MANAGER_PERMISSION = "warehouse:manager"

COMMANDS = {
    "0": {"target": "dashboard", "label": "Manager Command Dashboard"},
    "1": {"target": "exceptions", "label": "Exception Center"},
    "2": {"target": "dispatch", "label": "Dispatch Operations"},
    "3": {"target": "orders", "label": "Order Operations"},
    "4": {"target": "warehouse", "label": "Warehouse Operations"},
    "5": {"target": "documents", "label": "Documents"},
    "6": {"target": "alerts", "label": "Alerts & Tasks"},
    "7": {"target": "search", "label": "Search"},
    "8": {"target": "recent", "label": "Recent Transactions"},
    "9": {"target": "favorites", "label": "Favorites"},
    "U-2100": {"target": "dashboard", "label": "Manager Command Dashboard"},
    "U-1300": {"target": "exceptions", "label": "Exception Center"},
    "U-1310": {"target": "exceptions", "label": "Delivery Exceptions"},
    "U-1320": {"target": "exceptions", "label": "Pickup Exceptions"},
    "U-1700": {"target": "dispatch", "label": "Driver Dispatch Center"},
    "U-2000": {"target": "alerts", "label": "Alerts & Tasks Center"},
}


def _manager(access_code: str):
    if is_master(access_code):
        return {"role": "administrator", "manager_access": True}
    try:
        require_permission(access_code, MANAGER_PERMISSION)
    except HTTPException as exc:
        # Never downgrade this endpoint to general inventory permissions.
        if exc.status_code in (401, 403):
            raise HTTPException(status_code=403, detail="Warehouse Manager or higher access required")
        raise
    return {"role": "warehouse_manager", "manager_access": True}


@router.get("/warehouse/manager/session")
def manager_session(x_access_code: str = Header(default="")):
    result = _manager(x_access_code)
    return {**result, "permission": MANAGER_PERMISSION, "commands": COMMANDS}


@router.get("/warehouse/manager/commands")
def manager_commands(x_access_code: str = Header(default="")):
    _manager(x_access_code)
    return {"commands": COMMANDS}

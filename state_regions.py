"""Uganda National Grid 10-state geographic registry.

State polygons are built by dissolving current district polygons. Entebbe is a
protected postal enclave inside Kampala Metropolitan and is NOT the postal
center/prefix for the separate Lake Victoria state.
"""

STATE_REGIONS = {
    "KMP": {"name": "Kampala Metropolitan", "grid_prefix": "KLA", "postal_prefix": "20", "postal_center": "Kampala"},
    "LKV": {"name": "Lake Victoria", "grid_prefix": "MSK", "postal_prefix": "30", "postal_center": "Masaka"},
    "NIL": {"name": "Nile", "grid_prefix": "JIN", "postal_prefix": "22", "postal_center": "Jinja"},
    "WHS": {"name": "Western Highlands", "grid_prefix": "MBA", "postal_prefix": "23", "postal_center": "Mbarara"},
    "ELG": {"name": "Elgon", "grid_prefix": "MBL", "postal_prefix": "24", "postal_center": "Mbale"},
    "NSV": {"name": "Northern Savannah", "grid_prefix": "GUL", "postal_prefix": "25", "postal_center": "Gulu"},
    "WNL": {"name": "West Nile", "grid_prefix": "ARU", "postal_prefix": "26", "postal_center": "Arua"},
    "EPL": {"name": "Eastern Plains", "grid_prefix": "SOR", "postal_prefix": "27", "postal_center": "Soroti"},
    "KRM": {"name": "Karamoja", "grid_prefix": "MOR", "postal_prefix": "28", "postal_center": "Moroto"},
    "ALB": {"name": "Albertine", "grid_prefix": "HOI", "postal_prefix": "29", "postal_center": "Hoima"},
}

# Protected city-level postal enclave, geographically inside Kampala Metropolitan.
ENTEBBE_POSTAL = {
    "grid_prefix": "ENT",
    "postal_prefix": "21",
    "postal_center": "Entebbe",
    "protected_postal_codes": ["21401", "21402", "21403", "21404", "21405"],
}


def state_for_grid_prefix(prefix: str):
    value = str(prefix).strip().upper()
    for code, state in STATE_REGIONS.items():
        if state["grid_prefix"] == value:
            return {"code": code, **state}
    if value == ENTEBBE_POSTAL["grid_prefix"]:
        return {"code": "ENT", "name": "Entebbe", **ENTEBBE_POSTAL}
    return None


def state_for_postal_prefix(prefix: str):
    value = str(prefix).strip()
    for code, state in STATE_REGIONS.items():
        if state["postal_prefix"] == value:
            return {"code": code, **state}
    if value == ENTEBBE_POSTAL["postal_prefix"]:
        return {"code": "ENT", "name": "Entebbe", **ENTEBBE_POSTAL}
    return None


def validate_registry():
    assert len(STATE_REGIONS) == 10
    grid = [s["grid_prefix"] for s in STATE_REGIONS.values()]
    postal = [s["postal_prefix"] for s in STATE_REGIONS.values()]
    assert len(set(grid)) == 10
    assert len(set(postal)) == 10
    assert ENTEBBE_POSTAL["grid_prefix"] not in grid
    assert ENTEBBE_POSTAL["postal_prefix"] not in postal
    return True

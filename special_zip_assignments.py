"""Persistent assignments for UGAMAP national 00xxx special ZIP facilities."""
import json, os
from special_postal_zones import (
    SPECIAL_BLOCKS,
    SPECIAL_CATEGORY_ANCHORS,
    LEGACY_SPECIAL_RANGES,
    category_for_special_zip,
    special_categories,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE = os.environ.get("SPECIAL_ZIP_STORE", os.path.join(BASE_DIR, "special_zip_assignments.json"))

DEFAULT_ASSIGNMENTS = [
    {
        "zip_code": "00001",
        "category": "state_house",
        "name": "State House Uganda",
        "latitude": 0.05987,
        "longitude": 32.46913,
        "address": "Entebbe",
        "notes": "No fly zone",
        "special": True,
        "locked_anchor": True,
    }
]


def _runtime_load():
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _load():
    merged = {x["zip_code"]: dict(x) for x in DEFAULT_ASSIGNMENTS}
    for item in _runtime_load():
        code = str(item.get("zip_code", "")).zfill(5)
        if code:
            normalized = dict(item)
            normalized["zip_code"] = code
            normalized["special"] = True
            merged[code] = normalized
    return list(merged.values())


def _save(items):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def list_assignments():
    return _load()


def _block_codes(category):
    start, end = SPECIAL_BLOCKS[category]
    return [f"{n:05d}" for n in range(int(start), int(end) + 1)]


def _legacy_codes(category):
    values = []
    for start, end in LEGACY_SPECIAL_RANGES.get(category, []):
        values.extend(f"{n:05d}" for n in range(int(start), int(end) + 1))
    return values


def _anchor_for_category(category):
    for anchor, info in SPECIAL_CATEGORY_ANCHORS.items():
        if info.get("category") == category:
            return anchor
    return None


def valid_code_for_category(category, code):
    if category not in SPECIAL_BLOCKS:
        return False
    value = str(code or "").zfill(5)
    info = category_for_special_zip(value)
    return bool(info and info.get("category") == category)


def available_codes(category):
    if category not in SPECIAL_BLOCKS:
        return []
    used = {str(x.get("zip_code", "")).zfill(5) for x in _load()}
    result = []
    anchor = _anchor_for_category(category)
    if anchor and anchor not in used:
        result.append(anchor)
    # Preserve any unused legacy category codes, then allocate from the expanded block.
    result.extend(z for z in _legacy_codes(category) if z not in used and z not in result)
    result.extend(z for z in _block_codes(category) if z not in used and z not in result)
    return result


def next_code(category):
    codes = available_codes(category)
    return codes[0] if codes else None


def create_assignment(category, name, latitude, longitude, address="", notes="", zip_code=None):
    category = str(category or "").strip().lower()
    if category not in SPECIAL_BLOCKS:
        raise ValueError("Invalid special ZIP category")
    name = str(name or "").strip()
    if not name:
        raise ValueError("Facility name is required")
    code = str(zip_code or next_code(category) or "").zfill(5)
    if not code or not valid_code_for_category(category, code):
        raise ValueError("Special ZIP is outside this category")
    if code in {str(x.get("zip_code", "")).zfill(5) for x in _load()}:
        raise ValueError("Special ZIP is already assigned")
    item = {
        "zip_code": code,
        "category": category,
        "name": name,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "address": str(address or "").strip(),
        "notes": str(notes or "").strip(),
        "special": True,
    }
    runtime = _runtime_load()
    runtime.append(item)
    _save(runtime)
    return item


def update_assignment(old_zip_code, category=None, name=None, latitude=None, longitude=None, address=None, notes=None, zip_code=None):
    old = str(old_zip_code).zfill(5)
    all_items = _load()
    item = next((x for x in all_items if x.get("zip_code") == old), None)
    if not item:
        raise ValueError("Special ZIP assignment not found")
    new_category = str(category or item["category"]).strip().lower()
    if new_category not in SPECIAL_BLOCKS:
        raise ValueError("Invalid special ZIP category")
    new_code = str(zip_code or old).zfill(5)
    if not valid_code_for_category(new_category, new_code):
        raise ValueError("Special ZIP is outside this category")
    if new_code != old and new_code in {str(x.get("zip_code", "")).zfill(5) for x in all_items}:
        raise ValueError("Special ZIP is already assigned")
    updated = dict(item)
    updated["zip_code"] = new_code
    updated["category"] = new_category
    updated["special"] = True
    updated.pop("locked_anchor", None)
    if name is not None:
        v = str(name).strip()
        if not v:
            raise ValueError("Facility name is required")
        updated["name"] = v
    if latitude is not None:
        updated["latitude"] = float(latitude)
    if longitude is not None:
        updated["longitude"] = float(longitude)
    if address is not None:
        updated["address"] = str(address).strip()
    if notes is not None:
        updated["notes"] = str(notes).strip()
    runtime = [x for x in _runtime_load() if str(x.get("zip_code", "")).zfill(5) != old]
    runtime.append(updated)
    _save(runtime)
    return updated


def delete_assignment(zip_code):
    code = str(zip_code).zfill(5)
    if code in {x["zip_code"] for x in DEFAULT_ASSIGNMENTS if x.get("locked_anchor")}:
        return False
    runtime = _runtime_load()
    new = [x for x in runtime if str(x.get("zip_code", "")).zfill(5) != code]
    if len(new) == len(runtime):
        return False
    _save(new)
    return True


def category_catalog():
    result = []
    for item in special_categories():
        category = item["category"]
        result.append({
            **item,
            "available_count": len(available_codes(category)),
            "next_available_zip": next_code(category),
        })
    return result


def feature_collection():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in x.items() if k not in {"latitude", "longitude"}},
                "geometry": {"type": "Point", "coordinates": [x["longitude"], x["latitude"]]},
            }
            for x in _load()
        ],
    }

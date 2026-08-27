"""Persistent assignments for UGAMAP national 00xxx special ZIP facilities."""
import json, os
from special_postal_zones import SPECIAL_BLOCKS, SPECIAL_CATEGORY_ANCHORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(BASE_DIR, "special_zip_assignments.json")


def _load():
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def list_assignments():
    return _load()


def _block_codes(category):
    start, end = SPECIAL_BLOCKS[category]
    return [f"{n:05d}" for n in range(int(start), int(end) + 1)]


def available_codes(category):
    if category not in SPECIAL_BLOCKS:
        return []
    used = {x.get("zip_code") for x in _load()}
    return [z for z in _block_codes(category) if z not in used]


def next_code(category):
    codes = available_codes(category)
    return codes[0] if codes else None


def create_assignment(category, name, latitude, longitude, address="", notes="", zip_code=None):
    if category not in SPECIAL_BLOCKS:
        raise ValueError("Invalid special ZIP category")
    name = str(name or "").strip()
    if not name:
        raise ValueError("Facility name is required")
    code = str(zip_code or next_code(category) or "").zfill(5)
    if code not in available_codes(category):
        raise ValueError("Special ZIP is unavailable or outside this category")
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
    items = _load(); items.append(item); _save(items)
    return item


def delete_assignment(zip_code):
    code = str(zip_code).zfill(5)
    items = _load(); new = [x for x in items if x.get("zip_code") != code]
    if len(new) == len(items):
        return False
    _save(new); return True


def category_catalog():
    return [{"anchor": anchor, **info, "range": SPECIAL_BLOCKS[info["category"]]} for anchor, info in SPECIAL_CATEGORY_ANCHORS.items()]


def feature_collection():
    features=[]
    for x in _load():
        features.append({"type":"Feature","properties":{k:v for k,v in x.items() if k not in {"latitude","longitude"}},"geometry":{"type":"Point","coordinates":[x["longitude"],x["latitude"]]}})
    return {"type":"FeatureCollection","features":features}

"""
special_zip_assignments.py
Persistent special ZIP registry - monuments, national parks, government buildings.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_FILE = os.path.join(BASE_DIR, "special_zip_store.json")

CATEGORIES = {
    "government":    {"label": "Government Building", "range": (1, 299)},
    "national_park": {"label": "National Park", "range": (300, 599)},
    "monument":      {"label": "Monument / Heritage Site", "range": (600, 899)},
    "reserved":      {"label": "Reserved", "range": (900, 999)},
}

DEFAULT_SEED = {
    "00001": {
        "zip_code": "00001",
        "name": "State House Uganda",
        "category": "government",
        "latitude": 0.3654,
        "longitude": 32.4906,
        "address": "State House, Entebbe",
        "notes": "Official residence of the President of Uganda",
    }
}


def _load():
    if not os.path.exists(STORE_FILE):
        _save(DEFAULT_SEED)
        return dict(DEFAULT_SEED)
    try:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data):
    try:
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_store = _load()


def category_catalog():
    return [
        {
            "category": key,
            "label": info["label"],
            "range_start": str(info["range"][0]).zfill(5),
            "range_end": str(info["range"][1]).zfill(5),
        }
        for key, info in CATEGORIES.items()
    ]


def _next_code(category):
    start, end = CATEGORIES[category]["range"]
    used = set()
    for code in _store.keys():
        used.add(int(code))
    for n in range(start, end + 1):
        if n not in used:
            return str(n).zfill(5)
    raise ValueError("No free ZIP codes left in category '" + category + "'")


def list_assignments():
    return list(_store.values())


def create_assignment(category, name, latitude, longitude, address="", notes="", zip_code=None):
    if category not in CATEGORIES:
        raise ValueError("Invalid category '" + str(category) + "'")

    if not name or not str(name).strip():
        raise ValueError("Name is required")

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise TypeError("latitude and longitude must be numbers")

    if zip_code:
        code = str(zip_code).zfill(5)
        if code in _store:
            raise ValueError("ZIP code " + code + " is already assigned")
    else:
        code = _next_code(category)

    record = {
        "zip_code": code,
        "name": str(name).strip(),
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "address": address or "",
        "notes": notes or "",
    }

    _store[code] = record
    _save(_store)
    return record


def delete_assignment(zip_code):
    code = str(zip_code).zfill(5)
    if code not in _store:
        return False
    del _store[code]
    _save(_store)
    return True


def feature_collection():
    features = []
    for r in _store.values():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r["longitude"], r["latitude"]],
            },
            "properties": {
                "zip_code": r["zip_code"],
                "name": r["name"],
                "category": r["category"],
                "address": r.get("address", ""),
                "notes": r.get("notes", ""),
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
    }

"""
special_zip_assignments.py
Persistent special ZIP registry — monuments, national parks, government buildings.

Drop-in replacement: same function names your main.py already imports
(list_assignments, create_assignment, delete_assignment, category_catalog, feature_collection)
No changes needed anywhere else.

Saves every record to a JSON file on disk immediately after every change,
the same way entebbe_database.json works for regular addresses — so nothing
is lost on redeploy or restart.
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
        {"category": key, "label": info["label"],
         "range_start": str(info["range"][0]).zfill(5),
         "range_end": str(info["range"][1]).zfill(5)}
        for key, info in CATEGORIES.items()
    ]


def _next_code(category):
    start, end = CATEGORIES[category]["range"]
    used = {int(code) for code in _store.keys()}
    for n in range(start, end + 1):
        if n not in used:
            return str(n).zfill(5)
    raise ValueError(f"No free ZIP codes left in category '{category}'")


def list_assignments():
    return list(_store.values())


def create_assignment(category, name, latitude, longitude, address="", notes="", zip_code=None):
    if category not in CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {list(CATEGORIES.keys())}")
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
            raise ValueError(f"ZIP code {code} is already assigned")
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
    return {
        "type": "FeatureCollection",
        "features": [
            {
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
            }
            for r in _store.values()
        ],
    }
ot None:updated["latitude"]=float(latitude)
 if longitude is not None:updated["longitude"]=float(longitude)
 if address is not None:updated["address"]=str(address).strip()
 if notes is not None:updated["notes"]=str(notes).strip()
 if new_code!=old:
  if DATABASE_URL:_delete_db(old)
  else:_save_json([x for x in _runtime_load_json() if str(x.get("zip_code","")).zfill(5)!=old])
 _persist_item(updated);return updated
def delete_assignment(zip_code):
 code=str(zip_code).zfill(5)
 if code in {x["zip_code"] for x in DEFAULT_ASSIGNMENTS if x.get("locked_anchor")}:return False
 if DATABASE_URL:return bool(_delete_db(code))
 runtime=_runtime_load_json();new=[x for x in runtime if str(x.get("zip_code","")).zfill(5)!=code]
 if len(new)==len(runtime):return False
 _save_json(new);return True
def category_catalog():
 used={str(x.get("zip_code","")).zfill(5) for x in _load()};result=[]
 for anchor,info in SPECIAL_CATEGORY_ANCHORS.items():
  category=info["category"];codes=[anchor]+_legacy_codes(category)+_block_codes(category);available=[z for z in codes if z not in used]
  result.append({"anchor":anchor,**info,"range":SPECIAL_BLOCKS[category],"next_available":available[0] if available else None,"available_count":len(available),"persistent_backend":"postgresql" if DATABASE_URL else "json_fallback"})
 return result
def feature_collection():return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{k:v for k,v in x.items() if k not in {"latitude","longitude"}},"geometry":{"type":"Point","coordinates":[x["longitude"],x["latitude"]]}} for x in _load()]}
def persistence_status():return {"backend":"postgresql" if DATABASE_URL else "json_fallback","durable_across_redeploys":bool(DATABASE_URL),"database_configured":bool(DATABASE_URL)}

try:
 _init_db();_migrate_json_to_db()
except Exception as e:print("Special ZIP database init unavailable:",e)

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


def list_assignments(): return _load()


def _block_codes(category):
    start, end = SPECIAL_BLOCKS[category]
    return [f"{n:05d}" for n in range(int(start), int(end) + 1)]


def _anchor_for_category(category):
    for anchor, info in SPECIAL_CATEGORY_ANCHORS.items():
        if info.get("category") == category:
            return anchor
    return None


def valid_code_for_category(category, code):
    value = str(code or "").zfill(5)
    return value == _anchor_for_category(category) or value in _block_codes(category)


def available_codes(category):
    if category not in SPECIAL_BLOCKS: return []
    used = {x.get("zip_code") for x in _load()}
    result=[]
    anchor=_anchor_for_category(category)
    if anchor and anchor not in used: result.append(anchor)
    result.extend(z for z in _block_codes(category) if z not in used)
    return result


def next_code(category):
    codes=available_codes(category)
    return codes[0] if codes else None


def create_assignment(category, name, latitude, longitude, address="", notes="", zip_code=None):
    if category not in SPECIAL_BLOCKS: raise ValueError("Invalid special ZIP category")
    name=str(name or "").strip()
    if not name: raise ValueError("Facility name is required")
    code=str(zip_code or next_code(category) or "").zfill(5)
    if not valid_code_for_category(category, code): raise ValueError("Special ZIP is outside this category")
    if code in {x.get("zip_code") for x in _load()}: raise ValueError("Special ZIP is already assigned")
    item={"zip_code":code,"category":category,"name":name,"latitude":float(latitude),"longitude":float(longitude),"address":str(address or "").strip(),"notes":str(notes or "").strip(),"special":True}
    items=_load();items.append(item);_save(items);return item


def update_assignment(old_zip_code, category=None, name=None, latitude=None, longitude=None, address=None, notes=None, zip_code=None):
    old=str(old_zip_code).zfill(5);items=_load();item=next((x for x in items if x.get("zip_code")==old),None)
    if not item: raise ValueError("Special ZIP assignment not found")
    new_category=category or item["category"]
    if new_category not in SPECIAL_BLOCKS: raise ValueError("Invalid special ZIP category")
    new_code=str(zip_code or old).zfill(5)
    if not valid_code_for_category(new_category,new_code): raise ValueError("Special ZIP is outside this category")
    if new_code!=old and new_code in {x.get("zip_code") for x in items}: raise ValueError("Special ZIP is already assigned")
    item["zip_code"]=new_code;item["category"]=new_category
    if name is not None:
        v=str(name).strip()
        if not v: raise ValueError("Facility name is required")
        item["name"]=v
    if latitude is not None:item["latitude"]=float(latitude)
    if longitude is not None:item["longitude"]=float(longitude)
    if address is not None:item["address"]=str(address).strip()
    if notes is not None:item["notes"]=str(notes).strip()
    _save(items);return item


def delete_assignment(zip_code):
    code=str(zip_code).zfill(5);items=_load();new=[x for x in items if x.get("zip_code")!=code]
    if len(new)==len(items):return False
    _save(new);return True


def category_catalog():
    return [{"anchor":anchor,**info,"range":SPECIAL_BLOCKS[info["category"]]} for anchor,info in SPECIAL_CATEGORY_ANCHORS.items()]


def feature_collection():
    features=[]
    for x in _load():features.append({"type":"Feature","properties":{k:v for k,v in x.items() if k not in {"latitude","longitude"}},"geometry":{"type":"Point","coordinates":[x["longitude"],x["latitude"]]}})
    return {"type":"FeatureCollection","features":features}

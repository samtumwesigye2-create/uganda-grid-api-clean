"""Persistent assignments for UGAMAP national 00xxx special ZIP facilities.

When DATABASE_URL is configured, assignments are stored in PostgreSQL so Save
survives restarts, redeploys, and application updates. Local JSON is retained as
a development fallback only.
"""
import json, os
from special_postal_zones import SPECIAL_BLOCKS, SPECIAL_CATEGORY_ANCHORS, LEGACY_SPECIAL_RANGES

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
STORE=os.environ.get("SPECIAL_ZIP_STORE",os.path.join(BASE_DIR,"special_zip_assignments.json"))
DATABASE_URL=os.environ.get("DATABASE_URL","").strip()

DEFAULT_ASSIGNMENTS=[{
 "zip_code":"00001","category":"state_house","name":"State House Uganda",
 "latitude":0.05987,"longitude":32.46913,"address":"Entebbe",
 "notes":"No fly zone","special":True,"locked_anchor":True
}]


def _connect():
 if not DATABASE_URL:return None
 import psycopg2
 return psycopg2.connect(DATABASE_URL)


def _init_db():
 conn=_connect()
 if not conn:return False
 try:
  with conn:
   with conn.cursor() as cur:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS special_zip_assignments(
      zip_code VARCHAR(5) PRIMARY KEY,
      category VARCHAR(64) NOT NULL,
      name TEXT NOT NULL,
      latitude DOUBLE PRECISION NOT NULL,
      longitude DOUBLE PRECISION NOT NULL,
      address TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      special BOOLEAN NOT NULL DEFAULT TRUE,
      locked_anchor BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_special_zip_category ON special_zip_assignments(category);
    """)
  return True
 finally:conn.close()


def _runtime_load_json():
 try:
  with open(STORE,"r",encoding="utf-8") as f:
   data=json.load(f);return data if isinstance(data,list) else []
 except Exception:return []


def _save_json(items):
 with open(STORE,"w",encoding="utf-8") as f:json.dump(items,f,ensure_ascii=False,indent=2)


def _load_db():
 _init_db();conn=_connect()
 if not conn:return []
 try:
  with conn.cursor() as cur:
   cur.execute("SELECT zip_code,category,name,latitude,longitude,address,notes,special,locked_anchor FROM special_zip_assignments ORDER BY created_at,zip_code")
   return [{"zip_code":r[0],"category":r[1],"name":r[2],"latitude":r[3],"longitude":r[4],"address":r[5],"notes":r[6],"special":r[7],"locked_anchor":r[8]} for r in cur.fetchall()]
 finally:conn.close()


def _upsert_db(item):
 _init_db();conn=_connect()
 if not conn:return False
 try:
  with conn:
   with conn.cursor() as cur:
    cur.execute("""INSERT INTO special_zip_assignments(zip_code,category,name,latitude,longitude,address,notes,special,locked_anchor)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT(zip_code) DO UPDATE SET category=EXCLUDED.category,name=EXCLUDED.name,latitude=EXCLUDED.latitude,
    longitude=EXCLUDED.longitude,address=EXCLUDED.address,notes=EXCLUDED.notes,special=EXCLUDED.special,
    locked_anchor=EXCLUDED.locked_anchor,updated_at=NOW()""",
    (item["zip_code"],item["category"],item["name"],item["latitude"],item["longitude"],item.get("address",""),item.get("notes",""),True,bool(item.get("locked_anchor",False))))
  return True
 finally:conn.close()


def _delete_db(code):
 _init_db();conn=_connect()
 if not conn:return False
 try:
  with conn:
   with conn.cursor() as cur:
    cur.execute("DELETE FROM special_zip_assignments WHERE zip_code=%s",(code,));return cur.rowcount>0
 finally:conn.close()


def _load():
 merged={x["zip_code"]:dict(x) for x in DEFAULT_ASSIGNMENTS}
 try:
  runtime=_load_db() if DATABASE_URL else _runtime_load_json()
 except Exception as e:
  print("Special ZIP database read unavailable:",e);runtime=_runtime_load_json()
 for item in runtime:
  code=str(item.get("zip_code","")).zfill(5)
  if code:merged[code]={**item,"zip_code":code}
 return list(merged.values())


def list_assignments():return _load()

def _block_codes(category):
 start,end=SPECIAL_BLOCKS[category];return [f"{n:05d}" for n in range(int(start),int(end)+1)]

def _legacy_codes(category):
 out=[]
 for start,end in LEGACY_SPECIAL_RANGES.get(category,[]):out.extend(f"{n:05d}" for n in range(int(start),int(end)+1))
 return out

def _anchor_for_category(category):
 for anchor,info in SPECIAL_CATEGORY_ANCHORS.items():
  if info.get("category")==category:return anchor
 return None

def valid_code_for_category(category,code):
 value=str(code or "").zfill(5)
 return value==_anchor_for_category(category) or value in _legacy_codes(category) or value in _block_codes(category)

def available_codes(category):
 if category not in SPECIAL_BLOCKS:return []
 used={str(x.get("zip_code","")).zfill(5) for x in _load()};result=[];anchor=_anchor_for_category(category)
 if anchor and anchor not in used:result.append(anchor)
 result.extend(z for z in _legacy_codes(category) if z not in used)
 result.extend(z for z in _block_codes(category) if z not in used)
 return result

def next_code(category):
 codes=available_codes(category);return codes[0] if codes else None

def _persist_item(item):
 if DATABASE_URL:
  if not _upsert_db(item):raise ValueError("Persistent database unavailable")
 else:
  runtime=[x for x in _runtime_load_json() if str(x.get("zip_code","")).zfill(5)!=item["zip_code"]];runtime.append(item);_save_json(runtime)

def create_assignment(category,name,latitude,longitude,address="",notes="",zip_code=None):
 if category not in SPECIAL_BLOCKS:raise ValueError("Invalid special ZIP category")
 name=str(name or "").strip()
 if not name:raise ValueError("Facility name is required")
 code=str(zip_code or next_code(category) or "").zfill(5)
 if not valid_code_for_category(category,code):raise ValueError("Special ZIP is outside this category")
 if code in {str(x.get("zip_code","")).zfill(5) for x in _load()}:raise ValueError("Special ZIP is already assigned")
 item={"zip_code":code,"category":category,"name":name,"latitude":float(latitude),"longitude":float(longitude),"address":str(address or "").strip(),"notes":str(notes or "").strip(),"special":True}
 _persist_item(item);return item

def update_assignment(old_zip_code,category=None,name=None,latitude=None,longitude=None,address=None,notes=None,zip_code=None):
 old=str(old_zip_code).zfill(5);all_items=_load();item=next((x for x in all_items if x.get("zip_code")==old),None)
 if not item:raise ValueError("Special ZIP assignment not found")
 if item.get("locked_anchor") and old in {x["zip_code"] for x in DEFAULT_ASSIGNMENTS}:raise ValueError("Locked anchor assignment cannot be moved")
 new_category=category or item["category"]
 if new_category not in SPECIAL_BLOCKS:raise ValueError("Invalid special ZIP category")
 new_code=str(zip_code or old).zfill(5)
 if not valid_code_for_category(new_category,new_code):raise ValueError("Special ZIP is outside this category")
 if new_code!=old and new_code in {x.get("zip_code") for x in all_items}:raise ValueError("Special ZIP is already assigned")
 updated=dict(item);updated["zip_code"]=new_code;updated["category"]=new_category;updated.pop("locked_anchor",None)
 if name is not None:
  v=str(name).strip()
  if not v:raise ValueError("Facility name is required")
  updated["name"]=v
 if latitude is not None:updated["latitude"]=float(latitude)
 if longitude is not None:updated["longitude"]=float(longitude)
 if address is not None:updated["address"]=str(address).strip()
 if notes is not None:updated["notes"]=str(notes).strip()
 if DATABASE_URL and new_code!=old:_delete_db(old)
 elif not DATABASE_URL and new_code!=old:
  runtime=[x for x in _runtime_load_json() if str(x.get("zip_code","")).zfill(5)!=old];_save_json(runtime)
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
  category=info["category"];codes=[]
  if anchor:codes.append(anchor)
  codes+=_legacy_codes(category)+_block_codes(category)
  available=[z for z in codes if z not in used]
  result.append({"anchor":anchor,**info,"range":SPECIAL_BLOCKS[category],"next_available":available[0] if available else None,"available_count":len(available),"persistent_backend":"postgresql" if DATABASE_URL else "json_fallback"})
 return result

def feature_collection():return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{k:v for k,v in x.items() if k not in {"latitude","longitude"}},"geometry":{"type":"Point","coordinates":[x["longitude"],x["latitude"]]}} for x in _load()]}

try:_init_db()
except Exception as e:print("Special ZIP database init unavailable:",e)

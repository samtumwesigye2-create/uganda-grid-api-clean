"""Persistent manual ZIP polygons created from the admin map editor.

Manual geometry is authoritative for where a ZIP applies. Manual assignments now
validate against the finalized national ZIP registry instead of the retired
20xxx/29xxx regional reserve lists.
"""
import json, os
from shapely.geometry import shape, mapping, Point
from national_zip_registry import STATE_BLOCKS, lookup_zip

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
STORE=os.path.join(BASE_DIR,"manual_zip_assignments.json")
DATABASE_URL=os.environ.get("DATABASE_URL","").strip()

LEGACY_REGION_TO_STATE={
 "KLA":"KAMPALA_CENTRAL","ENT":"KAMPALA_CENTRAL","MSK":"VICTORIA_EQUATORIAL",
 "HOI":"ALBERTINE_RIFT","ARU":"WEST_NILE","MBA":"KATONGA_HIGHLAND",
 "JIN":"NILE_SOURCE","MBL":"ELGON_KARAMOJA","MOR":"ELGON_KARAMOJA",
 "SOR":"KYOGA_KWANIA","GUL":"ASWA_SAVANNAH"
}
LEGACY_STATE_CODE_TO_STATE={
 "KMP":"KAMPALA_CENTRAL","LKV":"VICTORIA_EQUATORIAL","ALB":"ALBERTINE_RIFT",
 "WNL":"WEST_NILE","WHS":"KATONGA_HIGHLAND","NIL":"NILE_SOURCE",
 "ELG":"ELGON_KARAMOJA","KRM":"ELGON_KARAMOJA","EPL":"KYOGA_KWANIA","NSV":"ASWA_SAVANNAH"
}

def _state_key(value):
 v=str(value or "").strip().upper().replace(" ","_")
 if v in STATE_BLOCKS:return v
 return LEGACY_REGION_TO_STATE.get(v) or LEGACY_STATE_CODE_TO_STATE.get(v)

def canonical_state_for_region(region):return _state_key(region)
def _canonicalize_item(item):
 x=dict(item);code=str(x.get("zip_code","")).strip().zfill(5);meta=lookup_zip(code) if code else None
 if meta and meta.get("state_key"):
  x["zip_code"]=code;x["postal_region"]=meta["state_key"];x["state_code"]=meta["state_key"];x["state_name"]=meta.get("state_name");x["district"]=meta.get("district");x["state_forced_by_zip"]=True
 return x

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
    cur.execute("""CREATE TABLE IF NOT EXISTS manual_zip_assignments(
    zip_code VARCHAR(16) PRIMARY KEY,postal_region VARCHAR(32) NOT NULL,state_code VARCHAR(32) NOT NULL,
    name TEXT NOT NULL,geometry JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
    CREATE INDEX IF NOT EXISTS idx_manual_zip_region ON manual_zip_assignments(postal_region);""")
  return True
 finally:conn.close()

def _load_json():
 try:
  with open(STORE,"r",encoding="utf-8") as f:return [_canonicalize_item(x) for x in json.load(f)]
 except Exception:return []
def _save_json(items):
 with open(STORE,"w",encoding="utf-8") as f:json.dump([_canonicalize_item(x) for x in items],f,ensure_ascii=False,indent=2)

def _upsert_db(item,overwrite=False):
 _init_db();conn=_connect()
 if not conn:return False
 try:
  with conn:
   with conn.cursor() as cur:
    if overwrite:
     cur.execute("""INSERT INTO manual_zip_assignments(zip_code,postal_region,state_code,name,geometry) VALUES(%s,%s,%s,%s,%s::jsonb)
     ON CONFLICT(zip_code) DO UPDATE SET postal_region=EXCLUDED.postal_region,state_code=EXCLUDED.state_code,name=EXCLUDED.name,geometry=EXCLUDED.geometry,updated_at=NOW()""",
     (item["zip_code"],item["postal_region"],item["state_code"],item["name"],json.dumps(item["geometry"])))
    else:
     cur.execute("""INSERT INTO manual_zip_assignments(zip_code,postal_region,state_code,name,geometry) VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(zip_code) DO NOTHING""",
     (item["zip_code"],item["postal_region"],item["state_code"],item["name"],json.dumps(item["geometry"])))
  return True
 finally:conn.close()

def _migrate_json_to_db():
 if not DATABASE_URL:return 0
 moved=0
 for item in _load_json():
  try:
   if item.get("zip_code") and item.get("geometry"):_upsert_db(item,overwrite=False);moved+=1
  except Exception as e:print("Manual ZIP migration item unavailable:",e)
 return moved

def _load():
 if not DATABASE_URL:return _load_json()
 conn=None
 try:
  _init_db();_migrate_json_to_db();conn=_connect()
  with conn.cursor() as cur:
   cur.execute("SELECT zip_code,postal_region,state_code,name,geometry FROM manual_zip_assignments ORDER BY created_at,zip_code");rows=cur.fetchall()
  return [_canonicalize_item({"zip_code":r[0],"postal_region":r[1],"state_code":r[2],"name":r[3],"geometry":r[4],"manual":True,"persistent":True}) for r in rows]
 except Exception as e:print("Manual ZIP database read unavailable:",e);return []
 finally:
  if conn:
   try:conn.close()
   except Exception:pass

def _delete_db(zip_code):
 _init_db();conn=_connect()
 if not conn:return None
 try:
  with conn:
   with conn.cursor() as cur:cur.execute("DELETE FROM manual_zip_assignments WHERE zip_code=%s",(zip_code,));return cur.rowcount>0
 finally:conn.close()

def list_assignments():return _load()
def available_reserves(region):
 """Compatibility endpoint: return currently unused active ZIPs in a finalized state block."""
 key=_state_key(region)
 if not key:return []
 used={str(x.get("zip_code","")).zfill(5) for x in _load()}
 values=[]
 for district,a,b in STATE_BLOCKS[key]["districts"]:
  for n in range(a,b+1):
   z=f"{n:05d}"
   if z not in used:values.append(z)
 return values

def _repair_polygon(geometry):
 try:
  geom=shape(geometry)
 except Exception:
  raise ValueError("Valid polygon geometry required")
 if geom.is_empty:raise ValueError("Valid polygon geometry required")
 if not geom.is_valid:
  try:geom=geom.buffer(0)
  except Exception:pass
 if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon","MultiPolygon"}:
  raise ValueError("Draw a simple boundary without crossing lines")
 return geom

def create_assignment(zip_code,region,state_code,name,geometry):
 zip_code=str(zip_code or "").strip().zfill(5)
 meta=lookup_zip(zip_code)
 if not meta:raise ValueError("ZIP is outside the finalized national registry")
 if meta.get("special_only"):raise ValueError("00xxx ZIPs are National Special ZIPs and cannot be assigned here")
 if meta.get("reserved") or not meta.get("ordinary_assignment_allowed"):raise ValueError("ZIP is reserved and cannot be manually assigned")
 owner=meta.get("state_key")
 requested_state=_state_key(region) or _state_key(state_code)
 if requested_state and requested_state!=owner:raise ValueError(f"ZIP {zip_code} belongs to {meta.get('state_name')} and cannot be assigned to another state")
 if zip_code in {str(x.get("zip_code","")).zfill(5) for x in _load()}:raise ValueError("ZIP already has a manual boundary")
 geom=_repair_polygon(geometry)
 item={"zip_code":zip_code,"postal_region":owner,"state_code":owner,"state_name":meta.get("state_name"),"district":meta.get("district"),"name":name.strip() or zip_code,"geometry":mapping(geom),"manual":True,"state_forced_by_zip":True,"persistent":bool(DATABASE_URL)}
 if DATABASE_URL:_upsert_db(item,overwrite=False)
 else:
  items=_load_json();items.append(item);_save_json(items)
 return item

def delete_assignment(zip_code):
 zip_code=str(zip_code).strip().zfill(5)
 if DATABASE_URL:return bool(_delete_db(zip_code))
 items=_load_json();new=[x for x in items if str(x.get("zip_code","")).zfill(5)!=zip_code]
 if len(new)==len(items):return False
 _save_json(new);return True

def match_point(latitude,longitude):
 p=Point(float(longitude),float(latitude))
 for item in reversed(_load()):
  try:
   if shape(item["geometry"]).covers(p):return _canonicalize_item(item)
  except Exception:pass
 return None

def feature_collection():return {"type":"FeatureCollection","features":[{"type":"Feature","properties":{k:v for k,v in x.items() if k!="geometry"},"geometry":x["geometry"]} for x in _load()]}
def persistence_status():return {"backend":"postgresql" if DATABASE_URL else "json_fallback","durable_across_redeploys":bool(DATABASE_URL),"database_configured":bool(DATABASE_URL)}

try:
 _init_db();_migrate_json_to_db()
except Exception as e:print("Manual ZIP database init unavailable:",e)

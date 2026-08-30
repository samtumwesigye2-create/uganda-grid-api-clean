"""Persistent manual ZIP polygons created from the admin map editor.

Manual geometry is authoritative for where a ZIP applies. When DATABASE_URL is
configured, PostgreSQL is the durable source of truth and survives application
restarts/redeploys. Existing JSON assignments are automatically migrated into
PostgreSQL without overwriting newer database records.
"""
import json, os
from shapely.geometry import shape, mapping, Point
from postal_zones import REGIONS

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
STORE=os.path.join(BASE_DIR,"manual_zip_assignments.json")
DATABASE_URL=os.environ.get("DATABASE_URL","").strip()

REGION_TO_STATE={"KLA":"KMP","JIN":"NIL","MBA":"WHS","MBL":"ELG","GUL":"NSV","ARU":"WNL","SOR":"EPL","MOR":"KRM","HOI":"ALB","MSK":"LKV","ENT":"KMP"}

def canonical_state_for_region(region):return REGION_TO_STATE.get(str(region or "").strip().upper())
def _canonicalize_item(item):
 x=dict(item);region=str(x.get("postal_region","")).strip().upper();owner=canonical_state_for_region(region)
 if owner:x["postal_region"]=region;x["state_code"]=owner;x["state_forced_by_zip"]=True
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
    zip_code VARCHAR(16) PRIMARY KEY,postal_region VARCHAR(16) NOT NULL,state_code VARCHAR(16) NOT NULL,
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
 region=str(region or "").strip().upper();r=REGIONS.get(region)
 if not r:return []
 used={x.get("zip_code") for x in _load()};return [z for z in r.get("reserve_zip_codes",[]) if z not in used]
def create_assignment(zip_code,region,state_code,name,geometry):
 region=str(region or "").strip().upper();zip_code=str(zip_code or "").strip();r=REGIONS.get(region)
 if not r or zip_code not in r.get("reserve_zip_codes",[]):raise ValueError("ZIP is not a reserve code for this region")
 if zip_code not in available_reserves(region):raise ValueError("Reserve ZIP already assigned")
 owner=canonical_state_for_region(region)
 if not owner:raise ValueError("Postal region has no registered state owner")
 supplied=str(state_code or "").strip().upper()
 if supplied and supplied!=owner:raise ValueError(f"ZIP {zip_code} belongs to state {owner} and cannot be assigned to {supplied}")
 geom=shape(geometry)
 if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon","MultiPolygon"}:raise ValueError("Valid polygon geometry required")
 item={"zip_code":zip_code,"postal_region":region,"state_code":owner,"name":name.strip() or zip_code,"geometry":mapping(geom),"manual":True,"state_forced_by_zip":True,"persistent":bool(DATABASE_URL)}
 if DATABASE_URL:_upsert_db(item,overwrite=False)
 else:
  items=_load_json();items.append(item);_save_json(items)
 return item
def delete_assignment(zip_code):
 if DATABASE_URL:return bool(_delete_db(zip_code))
 items=_load_json();new=[x for x in items if x.get("zip_code")!=zip_code]
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

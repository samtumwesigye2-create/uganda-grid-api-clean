"""Production application entrypoint.

Extends the existing Uganda National Grid FastAPI application with the finalized
national ZIP registry, protected Entebbe pilot compatibility, active National
Special ZIP namespace, ZIP-aware search, and district-grounded coordinate lookup.
"""

from fastapi import Query, HTTPException, Header
from main import app, addresses, special_zip_search_records, check_admin
from national_zip_api import router as national_zip_router
from national_zip_registry import lookup_zip
from national_zip_coordinate import district_allocation_for_coordinate
from special_postal_zones import category_for_special_zip, namespace_summary
from special_zip_assignments import list_assignments as list_special_zips, available_codes, category_catalog, persistence_status as special_persistence_status
from manual_zip_assignments import persistence_status as manual_persistence_status

app.include_router(national_zip_router)


def _special_assignment(zip_code):
    code=str(zip_code or "").strip().zfill(5)
    return next((x for x in list_special_zips() if str(x.get("zip_code","")).zfill(5)==code),None)


def _zip_search_result(query: str):
    q = str(query or "").strip()
    if not q.isdigit() or len(q) > 5:
        return None
    code=q.zfill(5)
    special_meta=category_for_special_zip(code)
    if special_meta:
        assigned=_special_assignment(code)
        return {
            "grid_id":code,"zip_code":code,
            "address":assigned.get("name") if assigned else "Unassigned National Special ZIP",
            "display_name":assigned.get("name") if assigned else f"National Special ZIP {code}",
            "special":True,"special_category":special_meta.get("category"),
            "assigned":bool(assigned),"assignment":assigned,
            "national_zip":True,
        }
    result = lookup_zip(code)
    if not result:
        return None
    return {
        "grid_id": result["zip_code"], "zip_code": result["zip_code"],
        "address": result.get("district") or "Reserved ZIP range",
        "display_name": f"{result.get('district')}, {result.get('state_name')} — ZIP {result['zip_code']}" if result.get("district") else f"Reserved ZIP {result['zip_code']}",
        "state_name": result.get("state_name"), "political_region": result.get("political_region"),
        "district": result.get("district"), "reserved": result.get("reserved", False),
        "reservation": result.get("reservation"), "national_zip": True,
        "data_gap": result.get("data_gap", False), "county_subsplit_flag": result.get("county_subsplit_flag", False),
    }

for route in list(app.router.routes):
    if getattr(route, "path", None) == "/search" and "GET" in getattr(route, "methods", set()):
        app.router.routes.remove(route)

@app.get("/search")
def national_search(q: str = Query(..., min_length=1)):
    x=q.strip().lower();results=[]
    zip_result=_zip_search_result(q)
    if zip_result:results.append(zip_result)
    special=[a for a in special_zip_search_records() if x in str(a.get("zip_code","")).lower() or x in str(a.get("address","")).lower() or x in str(a.get("locality","")).lower()]
    normal=[a for a in addresses if x in str(a.get("grid_id","")).lower() or x in str(a.get("address","")).lower() or x in str(a.get("zip_code","")).lower()]
    seen=set();merged=[]
    for item in results+special+normal:
        key=(str(item.get("grid_id","")),str(item.get("zip_code","")),str(item.get("address","")))
        if key in seen:continue
        seen.add(key);merged.append(item)
        if len(merged)>=50:break
    return {"count":len(merged),"results":merged}

@app.get("/special-zips/namespace")
def special_zip_namespace():return namespace_summary()

@app.get("/special-zips/{zip_code}")
def special_zip_lookup(zip_code:str):
    code=str(zip_code).strip().zfill(5);meta=category_for_special_zip(code)
    if not meta:raise HTTPException(status_code=404,detail="ZIP is not allocated in the National Special ZIP namespace")
    assigned=_special_assignment(code)
    return {"zip_code":code,"special":True,"category":meta.get("category"),"category_metadata":meta,"assigned":bool(assigned),"assignment":assigned}

@app.get("/admin/special-zips/categories/{category}/availability")
def special_zip_category_availability(category:str,limit:int=Query(default=25,ge=1,le=250),x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode);key=category.strip().lower();catalog={x["category"]:x for x in category_catalog()}
    if key not in catalog:raise HTTPException(status_code=404,detail="Unknown special ZIP category")
    codes=available_codes(key)
    return {"category":key,"metadata":catalog[key],"available_count":len(codes),"next_available":codes[0] if codes else None,"available_codes":codes[:limit]}

@app.get("/admin/persistence/status")
def admin_persistence_status(x_admin_passcode:str=Header(default="")):
    check_admin(x_admin_passcode)
    special=special_persistence_status();manual=manual_persistence_status()
    durable=bool(special.get("durable_across_redeploys") and manual.get("durable_across_redeploys"))
    return {"durable":durable,"special_zips":special,"manual_zips":manual,"message":"Saved permanently" if durable else "Local fallback only — not guaranteed across redeploys"}

@app.get("/coordinates/national-zip")
def national_zip_for_coordinates(lat: float = Query(...), lon: float = Query(...)):
    result = district_allocation_for_coordinate(lat, lon)
    if result is None:return {"latitude":lat,"longitude":lon,"matched":False,"assignment_ready":False,"detail":"Coordinates did not match a loaded Uganda district polygon"}
    return {"latitude":lat,"longitude":lon,"matched":True,**result}

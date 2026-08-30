"""Production application entrypoint."""

from fastapi import Query, HTTPException, Header
from fastapi.responses import Response
from main import app, addresses, special_zip_search_records, check_admin, SPECIAL_ZIP_ADMIN_FILE, ZIP_ADMIN_FILE
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


def _zip_search_result(query):
    q=str(query or "").strip()
    if not q.isdigit() or len(q)>5:return None
    code=q.zfill(5);special_meta=category_for_special_zip(code)
    if special_meta:
        assigned=_special_assignment(code)
        return {"grid_id":code,"zip_code":code,"address":assigned.get("name") if assigned else "Unassigned National Special ZIP","display_name":assigned.get("name") if assigned else f"National Special ZIP {code}","special":True,"special_category":special_meta.get("category"),"assigned":bool(assigned),"assignment":assigned,"national_zip":True}
    result=lookup_zip(code)
    if not result:return None
    return {"grid_id":result["zip_code"],"zip_code":result["zip_code"],"address":result.get("district") or "Reserved ZIP range","display_name":f"{result.get('district')}, {result.get('state_name')} — ZIP {result['zip_code']}" if result.get("district") else f"Reserved ZIP {result['zip_code']}","state_name":result.get("state_name"),"political_region":result.get("political_region"),"district":result.get("district"),"reserved":result.get("reserved",False),"reservation":result.get("reservation"),"national_zip":True,"data_gap":result.get("data_gap",False),"county_subsplit_flag":result.get("county_subsplit_flag",False)}

for route in list(app.router.routes):
    if getattr(route,"path",None)=="/search" and "GET" in getattr(route,"methods",set()):app.router.routes.remove(route)

@app.get("/search")
def national_search(q:str=Query(...,min_length=1)):
    x=q.strip().lower();results=[];zr=_zip_search_result(q)
    if zr:results.append(zr)
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
    check_admin(x_admin_passcode);special=special_persistence_status();manual=manual_persistence_status();durable=bool(special.get("durable_across_redeploys") and manual.get("durable_across_redeploys"))
    return {"durable":durable,"special_zips":special,"manual_zips":manual,"message":"Saved permanently" if durable else "Local fallback only — not guaranteed across redeploys"}

PERSISTENCE_UI="""<script>(function(){function el(id){return document.getElementById(id)}function show(t,ok){var s=el('status');if(!s)return;s.textContent=t;s.style.color=ok?'#7df0a5':'#ffd166'}function H(){var p=el('pass');return {'X-Admin-Passcode':p?p.value:''}}async function status(){try{var r=await fetch('/admin/persistence/status',{headers:H(),__skipVerify:true});if(!r.ok)return null;return await r.json()}catch(e){return null}}async function verify(url,code){var ps=await status();if(!ps||!ps.durable){show('⚠ Save completed, but durable PostgreSQL persistence is not confirmed',false);return false}try{var r=await fetch(url,{headers:H(),cache:'no-store',__skipVerify:true});if(!r.ok){show('⚠ Save returned success, but database read-back failed',false);return false}var d=await r.json(),rows=d.results||[],z=String(code||'').padStart(5,'0'),hit=rows.find(function(x){return String(x.zip_code||'').padStart(5,'0')===z});if(!hit){show('⚠ Save returned success, but ZIP '+z+' was not found on database read-back',false);return false}if(hit.persistent===false){show('⚠ ZIP '+z+' read back from local fallback, not PostgreSQL',false);return false}show('✓ Saved permanently — ZIP '+z+' verified from PostgreSQL',true);return true}catch(e){show('⚠ Save succeeded, but permanent read-back verification failed',false);return false}}async function initial(){var d=await status();if(!d)return;show(d.durable?'✓ PostgreSQL connected — saves are permanent across restarts and updates':'⚠ '+d.message,!!d.durable)}var p=el('pass');if(p){p.addEventListener('change',initial);p.addEventListener('blur',initial)}var nativeFetch=window.fetch.bind(window);window.fetch=async function(input,init){init=init||{};var skip=!!init.__skipVerify;if(skip){var c=Object.assign({},init);delete c.__skipVerify;return nativeFetch(input,c)}var r=await nativeFetch(input,init);try{var u=String(input||''),m=String(init.method||'GET').toUpperCase();if(r.ok&&m==='POST'&&(u==='/admin/special-zips'||u==='/admin/zips/manual')){var clone=r.clone(),body=await clone.json(),code=body&&body.zip_code;if(code)setTimeout(function(){verify(u==='/admin/special-zips'?'/admin/special-zips':'/admin/zips/manual',code)},80)}}catch(e){}return r};})();</script>"""

for route in list(app.router.routes):
    if getattr(route,"path",None) in {"/admin/special-zips/manage","/admin/zips"} and "GET" in getattr(route,"methods",set()):app.router.routes.remove(route)

def _admin_html(path):
    with open(path,"r",encoding="utf-8") as f:html=f.read()
    return html.replace("</body>",PERSISTENCE_UI+"</body>") if "</body>" in html else html+PERSISTENCE_UI

@app.get("/admin/special-zips/manage")
def special_zip_admin_page_persistent():return Response(content=_admin_html(SPECIAL_ZIP_ADMIN_FILE),media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})

@app.get("/admin/zips")
def zip_admin_page_persistent():return Response(content=_admin_html(ZIP_ADMIN_FILE),media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})

@app.get("/coordinates/national-zip")
def national_zip_for_coordinates(lat:float=Query(...),lon:float=Query(...)):
    result=district_allocation_for_coordinate(lat,lon)
    if result is None:return {"latitude":lat,"longitude":lon,"matched":False,"assignment_ready":False,"detail":"Coordinates did not match a loaded Uganda district polygon"}
    return {"latitude":lat,"longitude":lon,"matched":True,**result}

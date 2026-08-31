from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Optional

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/core", tags=["UGAMAP Core"])

_address_source: Callable[[], Iterable[dict[str, Any]]] = lambda: []
_state_lookup: Optional[Callable[[float, float], Any]] = None
_zip_lookup: Optional[Callable[[float, float], Any]] = None
_reports_source: Optional[Callable[[], Iterable[dict[str, Any]]]] = None
_report_create: Optional[Callable[[str, float, float, str], Any]] = None
_search_source: Optional[Callable[[str, int], Any]] = None
_address_lookup: Optional[Callable[[str], Any]] = None
_location_lookup: Optional[Callable[[float, float, float], Any]] = None


def configure_core(*, address_source, state_lookup=None, zip_lookup=None, reports_source=None,
                   report_create=None, search_source=None, address_lookup=None, location_lookup=None) -> None:
    global _address_source, _state_lookup, _zip_lookup, _reports_source, _report_create, _search_source, _address_lookup, _location_lookup
    _address_source = address_source
    _state_lookup = state_lookup
    _zip_lookup = zip_lookup
    _reports_source = reports_source
    _report_create = report_create
    _search_source = search_source
    _address_lookup = address_lookup
    _location_lookup = location_lookup


def _addresses():
    return list(_address_source() or [])


def _clean_text(value):
    if not isinstance(value, str): return value
    replacements={"â€”":"—","â€“":"–","â€˜":"‘","â€™":"’","â€œ":"“","â€":"”","Â ":" "}
    for broken,correct in replacements.items(): value=value.replace(broken,correct)
    return value


def _clean_payload(value):
    if isinstance(value,dict): return {k:_clean_payload(v) for k,v in value.items()}
    if isinstance(value,list): return [_clean_payload(v) for v in value]
    return _clean_text(value)


def _normalized_address(record):
    normalized={"grid_id":record.get("grid_id",""),"address":record.get("address") or record.get("display_name") or record.get("grid_id",""),"display_name":record.get("display_name") or record.get("address") or record.get("grid_id",""),"latitude":record.get("latitude"),"longitude":record.get("longitude"),"zip_code":record.get("zip_code"),"state_code":record.get("state_code"),"state_name":record.get("state_name"),"address_type":record.get("address_type"),**{k:v for k,v in record.items() if k not in {"grid_id","address","display_name","latitude","longitude","zip_code","state_code","state_name","address_type"}}}
    return _clean_payload(normalized)


def _haversine_m(lat1,lon1,lat2,lon2):
    r=6371000.0;p1,p2=math.radians(lat1),math.radians(lat2);dp,dl=math.radians(lat2-lat1),math.radians(lon2-lon1);a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))


def _decode_shape(encoded):
    index=lat=lon=0;out=[]
    while index<len(encoded):
        shift=result=0
        while True:
            b=ord(encoded[index])-63;index+=1;result|=(b&31)<<shift;shift+=5
            if b<32: break
        lat+=~(result>>1) if result&1 else result>>1;shift=result=0
        while True:
            b=ord(encoded[index])-63;index+=1;result|=(b&31)<<shift;shift+=5
            if b<32: break
        lon+=~(result>>1) if result&1 else result>>1;out.append([lat/1e6,lon/1e6])
    return out


@router.get("/status")
def core_status():
    return {"status":"ok","service":"UGAMAP Core","version":"1.5","records":len(_addresses()),"capabilities":["address","search","location","coordinate-resolution","routing","reports","report-submission"]}


@router.get("/address/{grid_id}")
def core_address(grid_id:str):
    key=grid_id.strip()
    if _address_lookup:
        record=_address_lookup(key)
        if record:return _normalized_address(dict(record))
    lowered=key.lower()
    for record in _addresses():
        if str(record.get("grid_id","")).strip().lower()==lowered:return _normalized_address(record)
    raise HTTPException(status_code=404,detail="UGAMAP location not found")


@router.get("/search")
def core_search(q:str=Query(...,min_length=1),limit:int=Query(20,ge=1,le=50)):
    if _search_source:
        payload=_search_source(q.strip(),limit);results=list(payload.get("results") or [])[:limit] if isinstance(payload,dict) else list(payload or [])[:limit];results=_clean_payload(results);return {"count":len(results),"results":results}
    key=q.strip().lower();matches=[]
    for record in _addresses():
        searchable=" ".join(str(record.get(f,"")) for f in ("grid_id","address","display_name","zip_code","state_name")).lower()
        if key in searchable:
            matches.append(_normalized_address(record))
            if len(matches)>=limit:break
    return {"count":len(matches),"results":matches}


@router.get("/location")
def core_location(lat:float=Query(...),lon:float=Query(...),tolerance_m:float=Query(15.0,ge=0.0,le=500.0)):
    if _location_lookup:
        payload=_location_lookup(lat,lon,tolerance_m)
        if payload is not None:return _clean_payload(dict(payload))
    state=_state_lookup(lat,lon) if _state_lookup else None
    if not state:raise HTTPException(status_code=400,detail="Coordinates are outside the validated Uganda state polygons")
    if isinstance(state,dict) and state.get("ambiguous"):raise HTTPException(status_code=409,detail="Coordinate lies on an ambiguous state boundary")
    return _clean_payload({"latitude":lat,"longitude":lon,"matched":False,"created":False,"tolerance_m":tolerance_m,"state":state,"postal":_zip_lookup(lat,lon) if _zip_lookup else None,"assignment_required":True})


@router.get("/route")
def core_route(start_lat:float,start_lon:float,dest_lat:float,dest_lon:float,mode:str=Query("driving",pattern="^(driving|walking|cycling|flight)$")):
    if mode=="flight":
        distance=_haversine_m(start_lat,start_lon,dest_lat,dest_lon);return {"mode":mode,"points":[[start_lat,start_lon],[dest_lat,dest_lon]],"distance_m":distance,"duration_s":distance/800000*3600,"maneuvers":[],"provider":"direct"}
    costing={"driving":"auto","walking":"pedestrian","cycling":"bicycle"}[mode];payload={"locations":[{"lat":start_lat,"lon":start_lon},{"lat":dest_lat,"lon":dest_lon}],"costing":costing,"units":"kilometers"}
    try:
        response=requests.post("https://valhalla1.openstreetmap.de/route",json=payload,timeout=10);response.raise_for_status();data=response.json()
    except (requests.RequestException,ValueError) as exc:raise HTTPException(status_code=503,detail="Routing service is temporarily unavailable") from exc
    leg=((data.get("trip") or {}).get("legs") or [None])[0]
    if not leg or not leg.get("shape"):raise HTTPException(status_code=404,detail="No route found")
    summary=leg.get("summary") or {};return _clean_payload({"mode":mode,"points":_decode_shape(leg["shape"]),"distance_m":float(summary.get("length") or 0)*1000,"duration_s":float(summary.get("time") or 0),"maneuvers":leg.get("maneuvers") or [],"provider":"valhalla"})


@router.get("/reports")
def core_reports():
    results=_clean_payload(list(_reports_source() or [])) if _reports_source else [];return {"count":len(results),"results":results}


def core_create_report(category:str,lat:float,lon:float,note:str=""):
    if not _report_create:raise HTTPException(status_code=503,detail="Report submission is unavailable")
    return _clean_payload(_report_create(category,lat,lon,note))

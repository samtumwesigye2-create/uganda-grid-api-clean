import json, os, urllib.parse
import requests
from fastapi.responses import Response

ZIPPER_BASE_URL=os.getenv('ZIPPER_BASE_URL','https://ung-zipper-production.up.railway.app').rstrip('/')
ROUTING_PATH='/routing/route'

def _json_response(payload,status=200,headers=None):
    h={'Cache-Control':'no-store'};h.update(headers or {})
    return Response(json.dumps(payload,default=str),status_code=status,media_type='application/json',headers=h)

def resolve_zipper(code:str):
    code=str(code or '').strip()
    if not code.isdigit():return None,400,'zip_must_be_numeric'
    code=code.zfill(5)
    try:
        r=requests.get(f'{ZIPPER_BASE_URL}/zipper/{code}',headers={'Accept':'application/json','User-Agent':'UGAMAP/ZIPPER-bridge'},timeout=5)
    except Exception as exc:return None,503,f'zipper_unavailable:{type(exc).__name__}'
    if r.status_code==404:return None,404,'zip_not_found'
    if r.status_code!=200:return None,502,f'zipper_http_{r.status_code}'
    try:data=r.json()
    except Exception:return None,502,'zipper_invalid_json'
    lat=data.get('latitude');lon=data.get('longitude')
    if lat is None or lon is None:return None,422,'zip_has_no_coordinates'
    try:data['latitude']=float(lat);data['longitude']=float(lon)
    except Exception:return None,422,'zip_coordinates_invalid'
    return data,200,None

async def maybe_handle_zipper_bridge(scope,receive):
    if scope.get('type')!='http' or scope.get('method')!='GET':return None
    path=scope.get('path') or ''
    if path.startswith('/destination/zip/'):
        code=path.rsplit('/',1)[-1]
        data,status,error=resolve_zipper(code)
        if error:return _json_response({'ok':False,'error':error,'zip':str(code).zfill(5)},status)
        return _json_response({'ok':True,'source':'UNG-ZIPPER','destination':data})
    if path!='/routing/to-zip':return None
    q=urllib.parse.parse_qs((scope.get('query_string') or b'').decode())
    def one(name):
        v=q.get(name);return v[0] if v else None
    code=one('zip') or one('code')
    try:start_lat=float(one('start_lat'));start_lon=float(one('start_lon'))
    except Exception:return _json_response({'ok':False,'error':'start_lat_and_start_lon_required'},400)
    dest,status,error=resolve_zipper(code or '')
    if error:return _json_response({'ok':False,'error':error,'zip':str(code or '').zfill(5)},status)
    payload={'locations':[{'lat':start_lat,'lon':start_lon},{'lat':dest['latitude'],'lon':dest['longitude']}],'costing':'auto','units':'kilometers'}
    return {'kind':'route_to_zip','zip':dest,'route_payload':json.dumps(payload).encode('utf-8')}

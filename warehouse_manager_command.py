"""Manager-only command authorization and Vector 5250 command metadata."""
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from auth import require_permission, is_master
from vector5250_records import router as vector_records_router
from vector5250_resilience import router as vector_resilience_router
from vector5250_jobs import router as vector_jobs_router
from vector5250_queues import router as vector_queues_router
from vector5250_messages import router as vector_messages_router
from vector5250_scheduler import router as vector_scheduler_router
from vector5250_profiles import router as vector_profiles_router

router = APIRouter(tags=["Vector 5250"])
router.include_router(vector_records_router); router.include_router(vector_resilience_router); router.include_router(vector_jobs_router); router.include_router(vector_queues_router); router.include_router(vector_messages_router); router.include_router(vector_scheduler_router); router.include_router(vector_profiles_router)
MANAGER_PERMISSION = "warehouse:manager"
COMMANDS={"0":{"target":"dashboard","label":"Manager Command Center"},"1":{"target":"exceptions","label":"Exception Center"},"2":{"target":"dispatch","label":"Dispatch Operations"},"3":{"target":"orders","label":"Order Management"},"4":{"target":"warehouse","label":"Warehouse Records"},"5":{"target":"documents","label":"Document Center"},"6":{"target":"alerts","label":"Alerts & Tasks"},"7":{"target":"search","label":"Record Search"},"8":{"target":"recent","label":"Recent Transactions"},"9":{"target":"favorites","label":"Favorites"},"U-2100":{"target":"dashboard","label":"Manager Command Center"},"U-1300":{"target":"exceptions","label":"Exception Center"},"U-1310":{"target":"exceptions","label":"Delivery Exceptions"},"U-1320":{"target":"exceptions","label":"Pickup Exceptions"},"U-1700":{"target":"dispatch","label":"Driver Dispatch Center"},"U-2000":{"target":"alerts","label":"Alerts & Tasks Center"},"U-9900":{"target":"system_status","label":"Vector System Status"},"U-9910":{"target":"active_jobs","label":"Work with Active Jobs"},"U-9920":{"target":"subsystems","label":"Work with Subsystems"},"U-9930":{"target":"jobq","label":"Work with Job Queues"},"U-9940":{"target":"outq","label":"Work with Output Queues"},"U-9950":{"target":"splf","label":"Work with Spooled Files"},"U-9960":{"target":"message_queues","label":"Work with Message Queues"},"U-9970":{"target":"operator_messages","label":"Display QSYSOPR Messages"},"U-9980":{"target":"send_message","label":"Send Vector Message"},"U-9990":{"target":"submitted_jobs","label":"Submit / Work with Jobs"},"U-9991":{"target":"job_schedule","label":"Work with Job Schedule Entries"},"U-9992":{"target":"user_profiles","label":"Work with User Profiles"}}
def _manager(access_code:str):
    if is_master(access_code): return {"role":"administrator","manager_access":True}
    try: require_permission(access_code,MANAGER_PERMISSION)
    except HTTPException as exc:
        if exc.status_code in (401,403): raise HTTPException(status_code=403,detail="Warehouse Manager or higher access required")
        raise
    return {"role":"warehouse_manager","manager_access":True}
@router.get("/vector5250",include_in_schema=False)
@router.get("/vector-5250",include_in_schema=False)
def page(): return Response(Path("vector5250.html").read_text(encoding="utf-8"),media_type="text/html",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
def js(name): return Response(Path(name).read_text(encoding="utf-8"),media_type="application/javascript",headers={"Cache-Control":"no-cache, no-store, must-revalidate"})
@router.get("/vector5250-runtime.js",include_in_schema=False)
def runtime(): return js("vector5250-runtime.js")
@router.get("/vector5250-jobs.js",include_in_schema=False)
def jobsjs(): return js("vector5250-jobs.js")
@router.get("/vector5250-queues.js",include_in_schema=False)
def queuesjs(): return js("vector5250-queues.js")
@router.get("/vector5250-messages.js",include_in_schema=False)
def messagesjs(): return js("vector5250-messages.js")
@router.get("/vector5250-scheduler.js",include_in_schema=False)
def schedulerjs(): return js("vector5250-scheduler.js")
@router.get("/vector5250-profiles.js",include_in_schema=False)
def profilesjs(): return js("vector5250-profiles.js")
@router.get("/warehouse/manager/session")
def session(x_access_code:str=Header(default="")):
    r=_manager(x_access_code); return {**r,"permission":MANAGER_PERMISSION,"commands":COMMANDS}
@router.get("/warehouse/manager/commands")
def commands(x_access_code:str=Header(default="")):
    _manager(x_access_code); return {"commands":COMMANDS}

import uuid

from fastapi import APIRouter, Form, Header, HTTPException

from user_profile_store import authenticate, change_password, create_session, create_user, revoke_session, update_profile, user_for_token

router = APIRouter(prefix="/account", tags=["UGAMAP Accounts"])


def _bearer(authorization: str) -> str:
    value=(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token=value[7:].strip()
    if not token: raise HTTPException(status_code=401, detail="Bearer token required")
    return token


def _current_user(authorization: str):
    token=_bearer(authorization)
    try:user=user_for_token(token)
    except RuntimeError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
    if not user:raise HTTPException(status_code=401,detail="Session is invalid or expired")
    return token,user


@router.post("/signup")
def signup(email:str=Form(...),password:str=Form(...),phone:str=Form(""),address:str=Form("")):
    try:
        user=create_user(str(uuid.uuid4()),password,email=email,phone=phone,address=address)
        session=create_session(user["id"])
        return {"user":user,**session}
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    except Exception as exc:
        msg=str(exc).lower()
        if "unique" in msg or "duplicate" in msg:raise HTTPException(status_code=409,detail="An account with that email already exists") from exc
        if "database_url" in msg:raise HTTPException(status_code=503,detail="Permanent user storage unavailable") from exc
        raise


@router.post("/login")
def login(email:str=Form(...),password:str=Form(...)):
    try:user=authenticate(email,password)
    except RuntimeError as exc:raise HTTPException(status_code=503,detail=str(exc)) from exc
    if not user:raise HTTPException(status_code=401,detail="Invalid email or password")
    return {"user":user,**create_session(user["id"])}


@router.get("/me")
def me(authorization:str=Header(default="")):
    _,user=_current_user(authorization);return user


@router.put("/me")
def update_me(email:str=Form(None),phone:str=Form(None),address:str=Form(None),authorization:str=Header(default="")):
    _,user=_current_user(authorization)
    try:return update_profile(user["id"],email=email,phone=phone,address=address,change_source="user")
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    except Exception as exc:
        msg=str(exc).lower()
        if "unique" in msg or "duplicate" in msg:raise HTTPException(status_code=409,detail="That email is already in use") from exc
        raise


@router.post("/password")
def password_change(current_password:str=Form(...),new_password:str=Form(...),authorization:str=Header(default="")):
    _,user=_current_user(authorization)
    try:change_password(user["id"],current_password,new_password)
    except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    return {"changed":True,"reauthenticate":True}


@router.post("/logout")
def logout(authorization:str=Header(default="")):
    token,_=_current_user(authorization);revoke_session(token);return {"logged_out":True}

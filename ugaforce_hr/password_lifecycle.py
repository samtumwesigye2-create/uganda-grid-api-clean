from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import psycopg2

from ugaforce_hr.security import DATABASE_URL, current_user, hash_password, token_hash, verify_password

router = APIRouter()
PASSWORD_PAGE = Path(__file__).resolve().parent / "password.html"


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


def _db() -> Any:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


@router.get("/account/password")
def password_page() -> FileResponse:
    return FileResponse(PASSWORD_PAGE, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.get("/api/v1/auth/password-state")
def password_state(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {
        "username": user["username"],
        "must_change_password": bool(user.get("must_change_password")),
    }


@router.post("/api/v1/auth/change-password")
def change_password(payload: PasswordChange, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password")

    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select password_hash from ugaforce_hr_users where id=%s and active=true for update",
                (user["id"],),
            )
            row = cur.fetchone()
            if not row or not verify_password(payload.current_password, row[0]):
                raise HTTPException(status_code=401, detail="Current password is incorrect")

            cur.execute(
                """
                update ugaforce_hr_users
                set password_hash=%s,
                    must_change_password=false,
                    password_changed_at=now(),
                    failed_signins=0,
                    locked_until=null,
                    updated_at=now()
                where id=%s
                """,
                (new_hash, user["id"]),
            )
            cur.execute(
                """
                update ugaforce_hr_sessions
                set revoked_at=now()
                where user_id=%s
                  and token_hash<>%s
                  and revoked_at is null
                """,
                (user["id"], token_hash(user["token"])),
            )
        conn.commit()

    return {"changed": True, "must_change_password": False}

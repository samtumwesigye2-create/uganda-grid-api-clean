from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
from fastapi import Header, HTTPException

DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")
PBKDF2_ITERATIONS = int(os.getenv("UGAFORCE_HR_PBKDF2_ITERATIONS", "310000"))
SESSION_HOURS = int(os.getenv("UGAFORCE_HR_SESSION_HOURS", "8"))
ROLE_RANK = {"EMPLOYEE": 10, "PAYROLL_ADMIN": 15, "MANAGER": 20, "HR_SPECIALIST": 30, "HR_MANAGER": 40, "HR_ADMIN": 50}


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(actual.hex(), expected_hex)
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(conn: Any, user_id: str) -> tuple[str, datetime]:
    token = "hr_" + secrets.token_urlsafe(36)
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    with conn.cursor() as cur:
        cur.execute("insert into ugaforce_hr_sessions(token_hash,user_id,expires_at) values(%s,%s,%s)", (token_hash(token), user_id, expires))
    return token, expires


def authenticate(username: str, password: str) -> dict[str, Any]:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("select id::text,username,password_hash,role_name,active,failed_signins,locked_until,employee_id::text from ugaforce_hr_users where lower(username)=lower(%s)", (username.strip(),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            uid, uname, phash, role, active, failed, locked_until, employee_id = row
            now = datetime.now(timezone.utc)
            if not active:
                raise HTTPException(status_code=403, detail="Account disabled")
            if locked_until and locked_until > now:
                raise HTTPException(status_code=423, detail="Account temporarily locked")
            if not verify_password(password, phash):
                failed = int(failed or 0) + 1
                lock = now + timedelta(minutes=15) if failed >= 5 else None
                cur.execute("update ugaforce_hr_users set failed_signins=%s,locked_until=%s,updated_at=now() where id=%s", (failed, lock, uid))
                raise HTTPException(status_code=401, detail="Invalid credentials")
            cur.execute("update ugaforce_hr_users set failed_signins=0,locked_until=null,last_signin=now(),updated_at=now() where id=%s", (uid,))
        token, expires = issue_session(conn, uid)
        conn.commit()
    return {"token": token, "expires_at": expires, "user": {"id": uid, "username": uname, "role": role, "employee_id": employee_id}}


def current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="HR database is not configured")
    value = authorization.strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = value.split(" ", 1)[1].strip()
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select u.id::text,u.username,u.role_name,u.employee_id::text,u.active,s.id::text
                from ugaforce_hr_sessions s join ugaforce_hr_users u on u.id=s.user_id
                where s.token_hash=%s and s.revoked_at is null and s.expires_at>now()
            """, (token_hash(token),))
            row = cur.fetchone()
    if not row or not row[4]:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"id": row[0], "username": row[1], "role": row[2], "employee_id": row[3], "session_id": row[5], "token": token}


def require_role(user: dict[str, Any], minimum: str) -> None:
    if ROLE_RANK.get(user.get("role", ""), 0) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail=f"{minimum} authority required")

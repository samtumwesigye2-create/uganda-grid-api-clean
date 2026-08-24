"""
users.py — Account system: signup, login, session tokens, profile.

Built to match what app.js already calls (the Account overlay in
index.html was built ahead of this backend, same pattern as several
other files in this project — the frontend was ready, this just needed
to exist):

  POST /auth/signup   {name, email, password, phone, address} -> user + token
  POST /auth/login     {email, password} -> user + token
  GET  /auth/me?token=...  -> user
  POST /auth/logout    (form: token)
  POST /profile         (json: token, name, phone, address) -> updated user

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only, no extra
dependency). Tokens are opaque random strings stored in a sessions
table, not JWTs — simplest thing that works and is easy to revoke
(logout just deletes the row).
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data_hub.db")

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ITERATIONS = 260_000


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def hash_password(password: str, salt: str = None) -> tuple:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()
    return digest, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    check, _ = hash_password(password, salt)
    return hmac.compare_digest(check, stored_hash)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
        (token, user_id, time.time()),
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: str):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    ).fetchone()
    conn.close()
    return row


def user_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"] or "",
        "address": row["address"] or "",
    }


class SignupBody(BaseModel):
    name: str
    email: str
    password: str
    phone: str = ""
    address: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileBody(BaseModel):
    token: str
    name: str = ""
    phone: str = ""
    address: str = ""


@router.post("/auth/signup")
def signup(body: SignupBody):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    conn = get_conn()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    password_hash, salt = hash_password(body.password)
    user_id = secrets.token_hex(16)
    conn.execute(
        """
        INSERT INTO users (id, name, email, password_hash, password_salt, phone, address, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (user_id, body.name.strip(), email, password_hash, salt, body.phone.strip(), body.address.strip(), time.time()),
    )
    conn.commit()
    conn.close()

    token = create_session(user_id)
    return {
        "token": token,
        "id": user_id,
        "name": body.name.strip(),
        "email": email,
        "phone": body.phone.strip(),
        "address": body.address.strip(),
    }


@router.post("/auth/login")
def login(body: LoginBody):
    email = body.email.strip().lower()
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not row or not verify_password(body.password, row["password_hash"], row["password_salt"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session(row["id"])
    return {"token": token, **user_to_dict(row)}


@router.get("/auth/me")
def me(token: str = ""):
    row = get_user_by_token(token)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_to_dict(row)


@router.post("/auth/logout")
async def logout(request: Request):
    form = await request.form()
    token = form.get("token", "")
    if token:
        conn = get_conn()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"status": "logged_out"}


@router.post("/profile")
def update_profile(body: ProfileBody):
    row = get_user_by_token(body.token)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    new_name = body.name.strip() or row["name"]
    new_phone = body.phone.strip()
    new_address = body.address.strip()

    conn = get_conn()
    conn.execute(
        "UPDATE users SET name = ?, phone = ?, address = ? WHERE id = ?",
        (new_name, new_phone, new_address, row["id"]),
    )
    conn.commit()
    conn.close()

    return {
        "id": row["id"],
        "name": new_name,
        "email": row["email"],
        "phone": new_phone,
        "address": new_address,
    }

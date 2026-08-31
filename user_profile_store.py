import base64
import hashlib
import hmac
import os
import secrets
import time

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("Permanent user storage unavailable: DATABASE_URL is not configured")
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def _hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    iterations = 310000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def init_user_profile_store():
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS ugamap_users(
                    id UUID PRIMARY KEY,
                    email TEXT UNIQUE,
                    phone TEXT,
                    address TEXT,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS ugamap_user_audit(
                    audit_id BIGSERIAL PRIMARY KEY,
                    user_id UUID NOT NULL,
                    field_name VARCHAR(32) NOT NULL,
                    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    change_source VARCHAR(32) NOT NULL DEFAULT 'user'
                );
                CREATE INDEX IF NOT EXISTS idx_ugamap_user_audit_user_time
                ON ugamap_user_audit(user_id, changed_at DESC);
                """)
        return True
    finally:
        conn.close()


def create_user(user_id: str, password: str, email: str = "", phone: str = "", address: str = ""):
    password_hash = _hash_password(password)
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ugamap_users(id,email,phone,address,password_hash)
                    VALUES(%s,%s,%s,%s,%s)
                """, (user_id, email or None, phone or None, address or None, password_hash))
        return get_user(user_id)
    finally:
        conn.close()


def get_user(user_id: str):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id,email,phone,address,EXTRACT(EPOCH FROM created_at),EXTRACT(EPOCH FROM updated_at) FROM ugamap_users WHERE id=%s", (user_id,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": str(r[0]), "email": r[1], "phone": r[2], "address": r[3],
                "created_at": float(r[4]), "updated_at": float(r[5])
            }
    finally:
        conn.close()


def update_profile(user_id: str, *, email=None, phone=None, address=None, change_source: str = "user"):
    changes = {k: v for k, v in {"email": email, "phone": phone, "address": address}.items() if v is not None}
    if not changes:
        return get_user(user_id)
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                for field, value in changes.items():
                    cur.execute(f"UPDATE ugamap_users SET {field}=%s,updated_at=NOW() WHERE id=%s", (value, user_id))
                    cur.execute("INSERT INTO ugamap_user_audit(user_id,field_name,change_source) VALUES(%s,%s,%s)", (user_id, field, change_source))
        return get_user(user_id)
    finally:
        conn.close()


def change_password(user_id: str, current_password: str, new_password: str):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM ugamap_users WHERE id=%s", (user_id,))
            r = cur.fetchone()
            if not r or not verify_password(current_password, r[0]):
                raise PermissionError("Current password is incorrect")
        new_hash = _hash_password(new_password)
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ugamap_users SET password_hash=%s,updated_at=NOW() WHERE id=%s", (new_hash, user_id))
                cur.execute("INSERT INTO ugamap_user_audit(user_id,field_name,change_source) VALUES(%s,'password','user')", (user_id,))
        return True
    finally:
        conn.close()


try:
    if DATABASE_URL:
        init_user_profile_store()
except Exception:
    pass

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

from .ugatu_models import EventRecord, TransactionRecord


class UGATUStore:
    """Persistence adapter. Uses Postgres when healthy, otherwise memory.

    A stale or temporarily unavailable DATABASE_URL must never crash the entire
    National Grid web process. UGATU falls back to in-process memory so UGAMAP,
    UGASHIP and the driver UI can still boot while the database connection is
    repaired.
    """

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.memory_transactions: Dict[str, TransactionRecord] = {}
        self.memory_events: Dict[str, EventRecord] = {}
        self.memory_idempotency: Dict[str, str] = {}
        self.memory_favorites: Dict[str, List[str]] = {}
        self.memory_recent: Dict[str, List[str]] = {}
        self.postgres_enabled = bool(self.database_url and psycopg2)
        self.persistence_error: Optional[str] = None
        if self.postgres_enabled:
            try:
                self._init_schema()
            except Exception as exc:
                # Production safety: UGATU is an add-on to the existing app and
                # must not make the whole Railway service unavailable because a
                # referenced Postgres service is missing or restarting.
                self.persistence_error = f"{type(exc).__name__}: {exc}"
                self.postgres_enabled = False

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def _init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS ugatu_transactions (
          transaction_id VARCHAR(40) PRIMARY KEY,
          ucode VARCHAR(10) NOT NULL,
          client_request_id VARCHAR(120) UNIQUE NOT NULL,
          actor_id VARCHAR(120), role VARCHAR(80), device_id VARCHAR(120),
          parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
          status VARCHAR(30) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS ugatu_events (
          event_id VARCHAR(40) PRIMARY KEY,
          event_type VARCHAR(120) NOT NULL,
          transaction_id VARCHAR(40) NOT NULL REFERENCES ugatu_transactions(transaction_id),
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          event_time TIMESTAMPTZ NOT NULL,
          received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ugatu_events_tx ON ugatu_events(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_ugatu_events_type_time ON ugatu_events(event_type,event_time DESC);
        CREATE TABLE IF NOT EXISTS ugatu_favorites (
          actor_id VARCHAR(120) NOT NULL,
          ucode VARCHAR(10) NOT NULL,
          position INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(actor_id, ucode)
        );
        CREATE TABLE IF NOT EXISTS ugatu_recent_actions (
          id BIGSERIAL PRIMARY KEY,
          actor_id VARCHAR(120) NOT NULL,
          ucode VARCHAR(10) NOT NULL,
          transaction_id VARCHAR(40),
          used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ugatu_recent_actor ON ugatu_recent_actions(actor_id, used_at DESC);
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)

    def save_transaction(self, tx: TransactionRecord) -> None:
        if not self.postgres_enabled:
            self.memory_transactions[tx.transaction_id] = tx
            self.memory_idempotency[tx.client_request_id] = tx.transaction_id
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ugatu_transactions
                    (transaction_id,ucode,client_request_id,actor_id,role,device_id,parameters,status,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (tx.transaction_id, tx.ucode, tx.client_request_id, tx.actor_id, tx.role,
                     tx.device_id, json.dumps(tx.parameters), tx.status, tx.created_at),
                )

    def save_event(self, event: EventRecord) -> None:
        if not self.postgres_enabled:
            self.memory_events[event.event_id] = event
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ugatu_events
                    (event_id,event_type,transaction_id,payload,event_time,received_at)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s)""",
                    (event.event_id, event.event_type, event.transaction_id,
                     json.dumps(event.payload), event.event_time, event.received_at),
                )

    def transaction_for_request(self, client_request_id: str) -> Optional[TransactionRecord]:
        if not self.postgres_enabled:
            txid = self.memory_idempotency.get(client_request_id)
            return self.memory_transactions.get(txid) if txid else None
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ugatu_transactions WHERE client_request_id=%s", (client_request_id,))
                row = cur.fetchone()
        return TransactionRecord(**dict(row)) if row else None

    def get_transaction(self, transaction_id: str) -> Optional[TransactionRecord]:
        if not self.postgres_enabled:
            return self.memory_transactions.get(transaction_id)
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ugatu_transactions WHERE transaction_id=%s", (transaction_id,))
                row = cur.fetchone()
        return TransactionRecord(**dict(row)) if row else None

    def get_event(self, event_id: str) -> Optional[EventRecord]:
        if not self.postgres_enabled:
            return self.memory_events.get(event_id)
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ugatu_events WHERE event_id=%s", (event_id,))
                row = cur.fetchone()
        return EventRecord(**dict(row)) if row else None

    def events_for_transaction(self, transaction_id: str) -> List[EventRecord]:
        if not self.postgres_enabled:
            return [e for e in self.memory_events.values() if e.transaction_id == transaction_id]
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ugatu_events WHERE transaction_id=%s ORDER BY event_time,event_id", (transaction_id,))
                rows = cur.fetchall()
        return [EventRecord(**dict(r)) for r in rows]

    def record_recent(self, actor_id: Optional[str], ucode: str, transaction_id: str) -> None:
        if not actor_id:
            return
        if not self.postgres_enabled:
            items = self.memory_recent.setdefault(actor_id, [])
            items[:] = [x for x in items if x != ucode]
            items.insert(0, ucode)
            del items[20:]
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO ugatu_recent_actions(actor_id,ucode,transaction_id) VALUES (%s,%s,%s)", (actor_id, ucode, transaction_id))

    def recent(self, actor_id: str, limit: int = 10) -> List[str]:
        limit = max(1, min(int(limit), 50))
        if not self.postgres_enabled:
            return self.memory_recent.get(actor_id, [])[:limit]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT ucode FROM ugatu_recent_actions WHERE actor_id=%s
                               GROUP BY ucode ORDER BY MAX(used_at) DESC LIMIT %s""", (actor_id, limit))
                return [r[0] for r in cur.fetchall()]

    def favorites(self, actor_id: str) -> List[str]:
        if not self.postgres_enabled:
            return self.memory_favorites.get(actor_id, [])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ucode FROM ugatu_favorites WHERE actor_id=%s ORDER BY position,ucode", (actor_id,))
                return [r[0] for r in cur.fetchall()]

    def set_favorites(self, actor_id: str, ucodes: List[str]) -> List[str]:
        clean = list(dict.fromkeys(ucodes))[:12]
        if not self.postgres_enabled:
            self.memory_favorites[actor_id] = clean
            return clean
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ugatu_favorites WHERE actor_id=%s", (actor_id,))
                for pos, code in enumerate(clean):
                    cur.execute("INSERT INTO ugatu_favorites(actor_id,ucode,position) VALUES (%s,%s,%s)", (actor_id, code, pos))
        return clean


store = UGATUStore()

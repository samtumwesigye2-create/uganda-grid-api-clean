from __future__ import annotations

import os
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("UGAFORCE_HR_DATABASE_URL") or os.getenv("DATABASE_URL")


def main() -> None:
    if not DATABASE_URL:
        raise SystemExit("UGAFORCE_HR_DATABASE_URL (or DATABASE_URL) is required")
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    if not migrations:
        raise SystemExit("No migrations found")
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("create table if not exists ugaforce_hr_schema_migrations (name text primary key, applied_at timestamptz not null default now())")
            for path in migrations:
                cur.execute("select 1 from ugaforce_hr_schema_migrations where name=%s", (path.name,))
                if cur.fetchone():
                    print(f"skip {path.name}")
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute("insert into ugaforce_hr_schema_migrations(name) values(%s)", (path.name,))
                print(f"applied {path.name}")
    print("UGAFORCE-HR migrations complete")


if __name__ == "__main__":
    main()

# UGAFORCE-HR deployment

UGAFORCE-HR is intentionally deployed as an independent Railway service from the same repository. It does not share operational tables with UGAMAP, UGASHIP, Warehouse, or Vector 5250.

## Railway service

Start command:

```bash
uvicorn ugaforce_hr_app:app --host 0.0.0.0 --port $PORT
```

Required variable:

- `UGAFORCE_HR_DATABASE_URL` — dedicated PostgreSQL connection string. `DATABASE_URL` is accepted as a fallback for local/dev use.

Optional variable:

- `UGAFORCE_HR_ALLOWED_ORIGINS` — comma-separated origins. In production set this to the final UGAFORCE-HR hostname rather than `*`.

## First migration

Run once against the dedicated database:

```bash
python ugaforce_hr/migrate.py
```

The migration runner records applied migrations in `ugaforce_hr_schema_migrations` and will not repeat them.

## Initial endpoints

- `/` — HR Command Center shell
- `/health` — service and PostgreSQL readiness
- `/api/v1/system/status` — API readiness
- `/api/v1/departments` — first core data endpoint

## Security boundary

Do not point `UGAFORCE_HR_DATABASE_URL` at the UGAMAP/UGASHIP/Vector database. HR is a separate system of record. Cross-system access will be introduced through controlled APIs and event/Data Relay messages.

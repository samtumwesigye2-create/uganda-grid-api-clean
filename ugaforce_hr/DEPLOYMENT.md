# UGAFORCE-HR deployment

UGAFORCE-HR is intentionally deployed as an independent Railway service from the same repository. It does not share operational tables with UGAMAP, UGASHIP, Warehouse, or Vector 5250.

## Railway service

Production start command:

```bash
bash ugaforce_hr/entrypoint.sh
```

The production entrypoint performs three ordered actions: validates required production environment settings, applies only pending PostgreSQL migrations, then starts `ugaforce_hr_runtime:app`. A missing database URL, missing bootstrap authority key, missing allowed-origin configuration, or wildcard CORS origin prevents production startup.

Direct development command:

```bash
uvicorn ugaforce_hr_runtime:app --host 0.0.0.0 --port $PORT
```

Required variables:

- `UGAFORCE_HR_DATABASE_URL` — dedicated PostgreSQL connection string. `DATABASE_URL` is accepted as a fallback for local/dev use.
- `UGAFORCE_HR_BOOTSTRAP_KEY` — one-time authority key used to create the first HR administrator. Do not use a hard-coded default.
- `UGAFORCE_HR_ALLOWED_ORIGINS` — comma-separated production origins. Wildcard `*` is rejected by the production readiness gate.

Future platform variables remain optional until UGACORE is deployed:

- `UGACORE_URL`
- `UGACORE_SERVICE_ID` — defaults to `ugaforce-hr`.
- `UGACORE_SERVICE_KEY`
- `UGACORE_TIMEOUT_SECONDS` — defaults to `1.5` seconds.

## Migrations

The production entrypoint automatically runs:

```bash
python ugaforce_hr/migrate.py
```

The migration runner records applied migrations in `ugaforce_hr_schema_migrations`, skips migrations already recorded, and applies new migrations in filename order. This allows a Railway deployment to bring the dedicated HR database forward before the API begins serving traffic.

For a manual migration-only run, use the same command above with the production HR database environment loaded.

## Acceptance

Repository/static acceptance:

```bash
python -m ugaforce_hr.acceptance
```

Production environment gate:

```bash
python -m ugaforce_hr.acceptance --environment
```

The production gate fails closed when the dedicated database configuration, bootstrap authority, or safe CORS origin configuration is absent.

## Production verification

After Railway reports the service healthy, verify `/health` first. Then exercise authentication and the protected HR modules using real authorized test accounts: People, Recruiting, Onboarding, Time & Attendance, Payroll & Benefits, Performance, Approvals, Analytics, Notifications, Offboarding, and Security Readiness. Do not treat repository acceptance alone as proof that the Railway database and deployed service are healthy.

## Security boundary

Do not point `UGAFORCE_HR_DATABASE_URL` at the UGAMAP, UGASHIP, Warehouse, Vector, Data Relay, or future UGACORE database. HR remains a separate system of record. Cross-system exchange occurs through controlled APIs/events, while UGACORE receives only cross-cutting platform signals such as monitoring and mirrored audit metadata.

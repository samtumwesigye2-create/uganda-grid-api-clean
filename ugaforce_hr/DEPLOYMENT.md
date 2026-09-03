# UGAFORCE-HR deployment

UGAFORCE-HR is intentionally deployed as an independent Railway service from the same repository. It does not share operational tables with UGAMAP, UGASHIP, Warehouse, or Vector 5250.

## Railway service

Start command:

```bash
uvicorn ugaforce_hr_runtime:app --host 0.0.0.0 --port $PORT
```

`ugaforce_hr_runtime.py` composes the standalone HR core with the Phase 2 People/RBAC routes and the fail-open UGACORE adapter. UGACORE is optional and must never be required for an HR transaction to succeed.

Required variables:

- `UGAFORCE_HR_DATABASE_URL` — dedicated PostgreSQL connection string. `DATABASE_URL` is accepted as a fallback for local/dev use.
- `UGAFORCE_HR_BOOTSTRAP_KEY` — one-time authority key used to create the first HR administrator. Do not use a hard-coded default.

Recommended production variable:

- `UGAFORCE_HR_ALLOWED_ORIGINS` — comma-separated allowed origins. Set this to the final UGAFORCE-HR hostname rather than `*`.

Future platform variables (optional until UGACORE is deployed):

- `UGACORE_URL`
- `UGACORE_SERVICE_ID` — defaults to `ugaforce-hr`.
- `UGACORE_SERVICE_KEY`
- `UGACORE_TIMEOUT_SECONDS` — defaults to `1.5` seconds.

## Migrations

Run against the dedicated HR database before first production start and after adding migrations:

```bash
python ugaforce_hr/migrate.py
```

The migration runner records applied migrations in `ugaforce_hr_schema_migrations` and does not repeat them. Current migrations establish the HR core, identity/session/RBAC controls, and People-directory indexes.

## Phase 2 endpoints

- `/` — authenticated HR Command Center and People directory
- `/health` — service and PostgreSQL readiness
- `/api/v1/auth/bootstrap` — one-time first administrator initialization
- `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/logout` — HR session lifecycle
- `/api/v1/dashboard` — live HR dashboard counts
- `/api/v1/departments` — organization structure
- `/api/v1/employees` — People directory and HR-managed employee records
- `/api/v1/employees/{employee_id}/account` — controlled user-account provisioning
- `/api/v1/profile-change-requests` — employee self-service change requests and HR review
- `/api/v1/audit` — local authoritative HR audit trail for HR management

## Security boundary

Do not point `UGAFORCE_HR_DATABASE_URL` at the UGAMAP, UGASHIP, Warehouse, Vector, Data Relay, or future UGACORE database. HR remains a separate system of record. Cross-system exchange occurs through controlled APIs/events, while UGACORE receives only cross-cutting platform signals such as monitoring and mirrored audit metadata.

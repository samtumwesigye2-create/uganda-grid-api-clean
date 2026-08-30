# Uganda National Grid — Phase 1 Clean Railway Deployment

This package is intentionally minimal. It only proves that the API can deploy and stay online.

Upload all files to the ROOT of a clean GitHub repository, for example `uganda-grid-api-clean`.

Railway should detect the Dockerfile automatically. Do not add PostgreSQL, DATABASE_URL, a custom Build Command, or a custom Start Command yet.

After deployment, generate a public domain and test:

- `/` should return `{"service":"Uganda National Grid API","status":"online","phase":1}`
- `/health` should return `{"status":"healthy"}`

Only after both work should PostgreSQL/PostGIS be added in Phase 2.
Deployment retry

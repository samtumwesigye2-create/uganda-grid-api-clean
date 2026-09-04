#!/usr/bin/env bash
set -euo pipefail

echo "UGAFORCE-HR: validating production environment"
python -m ugaforce_hr.acceptance --environment

echo "UGAFORCE-HR: applying pending database migrations"
python ugaforce_hr/migrate.py

echo "UGAFORCE-HR: starting API"
exec uvicorn ugaforce_hr_runtime:app --host 0.0.0.0 --port "${PORT:-8000}"

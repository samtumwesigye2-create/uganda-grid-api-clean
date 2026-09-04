from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REQUIRED_MODULES = [
    'ugaforce_hr.security','ugaforce_hr.people_admin','ugaforce_hr.recruiting',
    'ugaforce_hr.onboarding','ugaforce_hr.time_attendance','ugaforce_hr.payroll',
    'ugaforce_hr.performance','ugaforce_hr.workflow_analytics','ugaforce_hr.completion',
    'ugaforce_hr_runtime',
]
REQUIRED_ROUTES = {
    '/health','/api/v1/auth/login','/api/v1/employees','/api/v1/recruiting/metrics',
    '/api/v1/onboarding/metrics','/api/v1/time/metrics','/api/v1/payroll/metrics',
    '/api/v1/performance/metrics','/api/v1/approvals/inbox','/api/v1/analytics/executive',
    '/api/v1/notifications/me','/api/v1/offboarding','/api/v1/security/readiness',
}


def static_checks() -> dict[str, Any]:
    failures: list[str] = []
    migrations = sorted((ROOT / 'migrations').glob('*.sql'))
    names = [p.name for p in migrations]
    if len(names) != len(set(names)):
        failures.append('duplicate migration names')
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
        except Exception as exc:
            failures.append(f'import {module}: {exc}')
    try:
        from ugaforce_hr_runtime import app
        routes = {path for route in app.routes if (path := getattr(route, 'path', None))}
        missing = sorted(REQUIRED_ROUTES - routes)
        if missing:
            failures.append('missing routes: ' + ', '.join(missing))
    except Exception as exc:
        failures.append(f'route inspection failed: {exc}')
    return {'ok': not failures, 'failures': failures, 'migrations': names}


def environment_checks() -> dict[str, Any]:
    checks = {
        'database_url': bool(os.getenv('UGAFORCE_HR_DATABASE_URL') or os.getenv('DATABASE_URL')),
        'bootstrap_key': bool(os.getenv('UGAFORCE_HR_BOOTSTRAP_KEY')),
        'allowed_origins': bool(os.getenv('UGAFORCE_HR_ALLOWED_ORIGINS')),
    }
    return {'ok': all(checks.values()), 'checks': checks}


def main() -> None:
    result = static_checks()
    print('UGAFORCE-HR static acceptance:', result)
    if not result['ok']:
        raise SystemExit(1)
    print('UGAFORCE-HR environment readiness:', environment_checks())


if __name__ == '__main__':
    main()

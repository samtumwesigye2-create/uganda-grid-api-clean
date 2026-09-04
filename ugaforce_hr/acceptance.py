from __future__ import annotations

import argparse
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
ROUTER_MODULES = [
    'ugaforce_hr.people_admin','ugaforce_hr.recruiting','ugaforce_hr.onboarding',
    'ugaforce_hr.time_attendance','ugaforce_hr.payroll','ugaforce_hr.performance',
    'ugaforce_hr.workflow_analytics','ugaforce_hr.completion',
]


def _paths(obj: Any) -> set[str]:
    return {p for route in getattr(obj, 'routes', []) if (p := getattr(route, 'path', None))}


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
        routes = _paths(app)
        for name in ROUTER_MODULES:
            module = importlib.import_module(name)
            for attr in ('router', 'public_router'):
                candidate = getattr(module, attr, None)
                if candidate is not None:
                    routes |= _paths(candidate)
        missing = sorted(REQUIRED_ROUTES - routes)
        if missing:
            failures.append('missing routes: ' + ', '.join(missing))
    except Exception as exc:
        failures.append(f'route inspection failed: {exc}')
    return {'ok': not failures, 'failures': failures, 'migrations': names}


def environment_checks() -> dict[str, Any]:
    database_url = os.getenv('UGAFORCE_HR_DATABASE_URL') or os.getenv('DATABASE_URL')
    allowed_origins = [x.strip() for x in os.getenv('UGAFORCE_HR_ALLOWED_ORIGINS', '').split(',') if x.strip()]
    checks = {
        'database_url': bool(database_url),
        'bootstrap_key': bool(os.getenv('UGAFORCE_HR_BOOTSTRAP_KEY')),
        'allowed_origins': bool(allowed_origins) and '*' not in allowed_origins,
    }
    return {'ok': all(checks.values()), 'checks': checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', action='store_true', help='fail unless production environment variables are ready')
    args = parser.parse_args()
    result = static_checks()
    print('UGAFORCE-HR static acceptance:', result)
    if not result['ok']:
        raise SystemExit(1)
    environment = environment_checks()
    print('UGAFORCE-HR environment readiness:', environment)
    if args.environment and not environment['ok']:
        raise SystemExit('UGAFORCE-HR production environment is incomplete or unsafe')


if __name__ == '__main__':
    main()

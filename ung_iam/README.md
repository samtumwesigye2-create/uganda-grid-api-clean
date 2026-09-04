# UNG IAM — Identity & Access Management Platform

UNG IAM is the independent identity authority for the Uganda National Grid ecosystem.

## Responsibilities

- Human identities for employees and approved corporate users.
- Service identities for system-to-system access.
- Role-based access control and reusable permissions.
- Corporate-access classification used by systems such as WMS400Vector.
- Vendor/contractor identity classification for controlled external access.
- Session issuance and immediate revocation.
- Password change revokes existing sessions.
- Identity disablement immediately prevents further access.
- IAM audit history.

## Security design

Passwords are never stored in plaintext. The service uses scrypt with per-user random salts. Session credentials are opaque random tokens; only SHA-256 hashes of those tokens are stored in the IAM database.

UNG Sentinel remains the ecosystem security monitoring/protection authority. UNG IAM is the identity and authorization authority. Sentinel can monitor IAM events without owning identity records.

## Default roles

- `platform-admin`
- `security-admin`
- `corporate-user`
- `vendor`
- `service`

## Core API

- `GET /health`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET /v1/me`
- `GET /v1/identities`
- `POST /v1/identities`
- `PATCH /v1/identities/{identity_id}`
- `POST /v1/identities/{identity_id}/revoke`
- `GET /v1/roles`
- `POST /v1/roles`
- `GET /v1/audit`

## Bootstrap

Set these environment variables before first production startup:

- `UNG_IAM_BOOTSTRAP_EMAIL`
- `UNG_IAM_BOOTSTRAP_PASSWORD` (minimum 10 characters)
- `UNG_IAM_SESSION_TTL` (optional, defaults to 8 hours)
- `UNG_IAM_DB` (optional database path for the initial SQLite deployment)

Run independently with:

```bash
uvicorn ung_iam.app:app --host 0.0.0.0 --port 8000
```

## Migration rule

The existing `auth.py`, Vector sessions, and production access flows are not removed during the initial IAM build. Systems should migrate to UNG IAM one by one. Once all production consumers are verified, legacy passcode-based authorization can be retired rather than changed destructively in place.

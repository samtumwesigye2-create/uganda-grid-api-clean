# UNG Sentinel

**Official name:** UNG Sentinel — Security Monitoring & Protection Platform

UNG Sentinel is the independent security platform for the Uganda National Grid ecosystem. It groups the existing security monitoring, application protection, integrity, audit, MFA, and controlled external-system access capabilities under one platform identity without changing their existing production routes.

## Existing components grouped under Sentinel

- `security_layer.py` — central request protection, MFA, rate limiting, sensitive-route enforcement, security headers and security audit events.
- `security_integrity.py` — read-only integrity monitoring of critical application files, runtime hash-change detection, suspicious-signature checks and unsafe-permission checks.
- `integration_gateway.py` — controlled external integration gateway using configured connectors, HMAC-SHA256 signatures, idempotency controls, event queues, retries and integration audit records.

## Platform responsibilities

1. Identity and privileged-access monitoring.
2. MFA enforcement for sensitive operations when enabled.
3. Request-rate and malicious-payload protection.
4. Security event and denial auditing.
5. Application/file integrity monitoring.
6. External vendor, contractor, carrier, payment-provider and partner-system integration controls.
7. Signed inbound/outbound system events without direct partner database access.
8. Security status and operational-health reporting.

## Compatibility rule

UNG Sentinel is initially an architectural grouping and namespace. Existing routes and module imports remain compatible so production applications are not broken by the consolidation. Future Sentinel work should migrate implementation behind stable compatibility interfaces rather than renaming live routes destructively.

## Registry classification

**Independent top-level system:** Yes

**System type:** Security Monitoring & Protection Platform

**Short name:** Sentinel

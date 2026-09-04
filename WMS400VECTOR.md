# WMS400Vector

**Official name:** WMS400Vector — Corporate Live System of Record

WMS400Vector is the corporate-access-only live system of record for Uganda National Grid operations. It succeeds the VECTOR5250 product name while preserving the existing Vector implementation and data behavior.

## Access classification

Corporate access only. WMS400Vector is not a public, customer, driver, or general warehouse-worker application. Access remains permission controlled.

## Existing implementation retained

The current `vector5250*` files, `/vector5250/api/*` endpoints, and `vector5250.db` remain compatibility implementation identifiers during migration. They must not be destructively renamed until all imports, routes, clients, stored records and production dependencies have been migrated and verified.

## Core responsibilities

- Authoritative live operational records.
- Manager/corporate command center.
- Record inquiry, creation, display and controlled changes.
- Order and pickup records.
- Dispatch and warehouse records.
- Delivery/pickup and chain-of-custody documents.
- Exception and alert records.
- Jobs, queues, messages and scheduling.
- Record locking/concurrency control.
- Transaction journals and audit/recent-transaction history.

## Relationship to UGATU

UGATU is the transaction/U-Code execution layer. WMS400Vector is the corporate live system-of-record and operational terminal. They are complementary systems and should not be merged.

## Migration rule

All new user-facing naming should use `WMS400Vector`. Existing `VECTOR5250` implementation names are compatibility aliases until a controlled production migration is completed.

## Registry classification

**Independent top-level system:** Yes

**System type:** Corporate Live System of Record

**Short name:** WMS400Vector

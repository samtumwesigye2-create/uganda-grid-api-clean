# Vector 5250 Integration

Vector 5250 is an independent enterprise operations system and a system of record inside the Uganda National Grid ecosystem. Integration must not strip Vector 5250 of its own persistence, transaction rules, command set, custody state, audit trail, or operational responsibilities.

## Architecture

Vector 5250 UI -> Vector 5250 application services -> Vector 5250 system-of-record database -> Vector 5250 transaction/event/custody journal -> Data Relay monitoring -> backup replication service/database -> authorized ecosystem integrations.

Shared platform services may be reused where appropriate (for example identity/security, UGAMAP geography/routing, document services, and the signed Integration Gateway), but Vector 5250 remains authoritative for the records it owns.

## System-of-record boundary

Vector 5250 owns its enterprise operations records and persists them independently in its own database. Warehouse/UGASHIP may consume or publish authorized events through relay/API boundaries, but Vector 5250 is not a thin UI over `data_hub.db` and does not depend on Warehouse/UGASHIP as its source of truth.

No direct cross-system database writes are allowed. Synchronization is event/API based and preserves source identity, timestamps, client request IDs/idempotency, and audit history.

## Backup and integrity boundary

Every important Vector 5250 operational fact is committed to Vector's primary database first. The same fact is then replicated through the existing backup synchronization service using source identity `VECTOR5250`. That service is the authorized path to the backup database; Vector does not bypass the service with direct cross-database writes.

Backup failure must never silently rewrite or replace the Vector primary record. Backup client status exposes successful, failed, queued and dropped synchronization state so reconciliation can detect integrity gaps. Data Relay separately receives Vector operational events for monitoring, anomaly detection and integrity/observability purposes.

This produces three distinct integrity roles:

- Primary truth: Vector 5250 database.
- Recovery replica: backup database through the backup synchronization service.
- Monitoring/integrity telemetry: Data Relay.

## UGATU boundary

UGATU U-Codes are not renamed, replaced, or rewritten by Vector 5250. Vector 5250 keeps its own operator commands such as MIGO, MB51, MB52, MI01, MI04, MB5T, VL06O and LT03, plus Vector-native commands such as VRCV, VSCAN, VCUST, VADJ, VMOVE and VHOLD.

Where an operational event needs to enter UGATU, a separate interoperability adapter may translate that Vector event to an existing UGATU U-Code. The adapter is a boundary mapping only; it does not modify the UGATU registry and it does not make UGATU the internal command system of Vector 5250.

## Relay monitoring

Vector 5250 emits operational, audit, health and integration events to the existing Data Relay. Relay monitoring is observability/integration, not ownership: the relay does not replace Vector 5250 persistence or the backup database.

## Production paths

- `/vector5250` — Vector 5250 terminal UI
- `/api/vector5250/status` — Vector status, system-of-record and backup state
- `/api/vector5250/session` — authorized sign-on
- `/api/vector5250/dashboard` — Vector-owned operational dashboard
- `/api/vector5250/commands` — Vector command catalog
- `/api/vector5250/resolve/{command}` — Vector command resolver
- `/api/vector5250/receiving` — inbound receipt posting
- `/api/vector5250/scan` — package/freight/pallet/location scans
- `/api/vector5250/custody/{object_code}` — Vector custody history
- `/api/vector5250/backup-status` — Vector backup replication health
- `/api/vector5250/inventory` — inventory lookup by warehouse/SKU
- `/api/vector5250/inventory/{sku}/movements` — immutable movement history
- `/api/vector5250/inventory/move` — controlled bin/location movement
- `/api/vector5250/inventory/adjust` — explicit inventory adjustment
- `/api/vector5250/cycle-counts` — create physical count
- `/api/vector5250/cycle-counts/complete` — record physical count and variance
- `/api/vector5250/inventory/hold` — place/release inventory hold

## Migration policy for the original prototype

The original prototype contains inbound, outbound, inventory, purchasing, cycle count, MRP, MES, transportation, PLM, EAM, analytics and reporting responsibilities. These responsibilities remain Vector 5250 responsibilities while the prototype is hardened for production.

1. Replace browser-only prototype persistence with Vector 5250 server-side persistence, not Warehouse/UGASHIP persistence.
2. Preserve Vector 5250 workflows, commands and business rules.
3. Use shared security/identity where useful without making Vector dependent on another application's operational database.
4. Emit monitored events through Data Relay and replicate operational facts through the backup service/database.
5. Keep UGATU translation at the interoperability boundary only.
6. Keep the 5250 visual/keyboard workflow as the advanced operator experience.

## Phase 1

Phase 1 established Vector 5250 as an independent system of record, its database/event journal, relay monitoring, command catalog, shared sign-on boundary, Railway mount and explicit UGATU isolation.

## Phase 2

Phase 2 added inbound receiving, package/freight/pallet/location scanning, custody history, transaction idempotency, Vector inventory receipt posting, Relay emission and backup replication/status visibility.

## Phase 3

Phase 3 adds Vector-native inventory control:

- Inventory lookup by warehouse/SKU with bin/location quantities.
- Immutable movement journal for receipts, moves and adjustments.
- Controlled location-to-location moves with quantity validation.
- Physical cycle-count creation and completion.
- Variance capture without silently changing stock; adjustment is a separate explicit transaction.
- Explicit inventory adjustments with non-negative stock protection.
- Inventory hold/release records for quality, damage or operational review.
- Dashboard alerts for open counts and active holds.
- Relay monitoring and backup replication for inventory movements, cycle counts and holds.

Outbound/loading, transfers, returns, purchasing/MRP and MES/EAM remain subsequent Vector phases and are not absorbed into another system.

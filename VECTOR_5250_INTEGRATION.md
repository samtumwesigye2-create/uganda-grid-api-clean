# Vector 5250 Integration

Vector 5250 is an independent enterprise operations system and a system of record inside the Uganda National Grid ecosystem. Integration must not strip Vector 5250 of its own persistence, transaction rules, command set, audit trail, or operational responsibilities.

## Architecture

Vector 5250 UI -> Vector 5250 application services -> Vector 5250 system-of-record database -> Vector 5250 event/audit log -> Data Relay monitoring/event exchange -> authorized ecosystem consumers.

Shared platform services may be reused where appropriate (for example identity/security, UGAMAP geography/routing, document services, and the signed Integration Gateway), but Vector 5250 remains authoritative for the records it owns.

## System-of-record boundary

Vector 5250 owns its enterprise operations records and must persist them independently. Warehouse/UGASHIP may consume or publish authorized events through the relay/integration boundary, but Vector 5250 is not a thin UI over `data_hub.db` and does not depend on Warehouse/UGASHIP as its source of truth.

No direct cross-system database writes are allowed. Synchronization is event/API based and must preserve source-system identity, timestamps, idempotency keys, and audit history.

## UGATU boundary

UGATU U-Codes are not renamed, replaced, or rewritten by Vector 5250. Vector 5250 keeps its own operator commands such as MIGO, MB51, MB52, MI01, MI04, MB5T, VL06O and LT03.

Where an operational event needs to enter UGATU, a separate interoperability adapter may translate that Vector event to an existing UGATU U-Code. The adapter is a boundary mapping only; it does not modify the UGATU registry and it does not make UGATU the internal command system of Vector 5250.

## Relay monitoring

Vector 5250 emits operational, audit, health, and integration events to the existing Data Relay. Relay monitoring is observability/integration, not ownership: the relay does not replace Vector 5250 persistence.

## Production paths

- `/vector5250` — Vector 5250 terminal UI
- `/api/vector5250/status` — Vector status and system-of-record state
- `/api/vector5250/session` — authorized sign-on
- `/api/vector5250/dashboard` — Vector-owned operational dashboard
- `/api/vector5250/commands` — Vector command catalog
- `/api/vector5250/resolve/{command}` — Vector command resolver

## Migration policy for the original prototype

The original prototype contains inbound, outbound, inventory, purchasing, cycle count, MRP, MES, transportation, PLM, EAM, analytics and reporting responsibilities. These responsibilities remain Vector 5250 responsibilities while the prototype is hardened for production.

1. Replace browser-only prototype persistence with Vector 5250 server-side persistence, not Warehouse/UGASHIP persistence.
2. Preserve Vector 5250 workflows, commands and business rules.
3. Use shared security/identity where useful without making Vector dependent on another application's operational database.
4. Emit monitored events through Data Relay and use the signed Integration Gateway for external partners where appropriate.
5. Keep UGATU translation at the interoperability boundary only.
6. Keep the 5250 visual/keyboard workflow as the advanced operator experience.

## Phase 1

Phase 1 establishes Vector 5250 as an independent system of record, its database and event journal, relay monitoring, command catalog, shared sign-on boundary, Railway mount, and explicit UGATU isolation.

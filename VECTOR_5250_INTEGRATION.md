# Vector 5250 Integration

Vector 5250 is the enterprise warehouse/operator console for the Uganda National Grid ecosystem. It keeps the green-screen / 5250 operating style while using the existing ecosystem as the system of record.

## Architecture

Vector 5250 UI -> shared staff RBAC -> existing Warehouse/UGASHIP services and `data_hub.db` -> UGATU command/event layer -> UGAMAP for geography/routing -> UGA Integration Gateway for external systems.

Vector 5250 must not maintain a separate production warehouse database, separate production user/password table, or direct arbitrary outbound webhooks.

## Production paths

- `/vector5250` — Vector 5250 terminal UI
- `/api/vector5250/status` — integration status
- `/api/vector5250/session` — shared staff authorization check
- `/api/vector5250/dashboard` — existing warehouse control-tower data
- `/api/vector5250/commands` — Vector/SAP-style aliases mapped to UGATU
- `/api/vector5250/resolve/{command}` — resolve alias to canonical UGATU identity

## Command policy

Legacy/SAP-like transaction names are aliases for trained operators. UGATU remains canonical and immutable for execution, audit and integration. Current first-pass aliases include MIGO, MB51, MB52, MI01, MI04, MB5T, VL06O, LT03 and ZV5250.

## Migration policy for the original prototype

The original prototype contains valuable screens for inbound, outbound, inventory, purchasing, cycle count, MRP, MES, transportation, PLM, EAM, analytics and reporting. Those screens should be migrated incrementally. During migration:

1. Replace prototype `window.storage` persistence with existing warehouse/UGASHIP APIs.
2. Remove hard-coded/quick-login users and rely on shared staff RBAC.
3. Route operational commands through UGATU rather than creating a second transaction system.
4. Route external events through the signed UGA Integration Gateway rather than direct arbitrary webhooks.
5. Keep the 5250 visual/keyboard workflow as the advanced operator experience.

## Phase 1

Phase 1 installs the renamed Vector 5250 shell, shared authentication, live warehouse dashboard, command alias resolver and Railway mount. It does not duplicate inventory or custody truth.

Next phases migrate transaction screens in this order: inbound/receiving -> scan/custody -> inventory -> outbound/loading -> transfers -> returns -> purchasing/MRP -> MES/EAM -> analytics.

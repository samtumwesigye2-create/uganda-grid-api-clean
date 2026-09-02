# UGAMAP Incident Records

This folder defines the permanent incident-record subsystem for UGAMAP.

Runtime incident records are stored in PostgreSQL, not in GitHub files or process memory. The durable table is `ugamap_incidents`; media is stored in PostgreSQL `BYTEA`, and every administrative/community change is written to the incident audit log.

Policy:
- incident records do not expire automatically;
- incident records are not silently deleted;
- a resolved incident remains in administrative history;
- public map visibility is controlled by status, not deletion;
- changes are durable only after PostgreSQL confirms the write;
- if durable storage is unavailable, the application must reject the write rather than pretend it was saved;
- deletion, if later enabled, must be an explicit authenticated administrator action and should be audited.

Implementation is currently provided by `incident_store.py` and the UGAMAP production entrypoint. This directory is the permanent home for incident schema, migration, retention and audit documentation as that subsystem grows.

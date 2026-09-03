from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readiness_is_bound_to_current_shift_and_vehicle():
    src = (ROOT / "ugatu" / "ugatu_driver_dashboard.py").read_text()
    assert "created_at>=?" in src
    assert "shift[\"started_at\"]" in src
    assert "PRE_TRIP_REQUIRED_THIS_SHIFT" in src
    assert "POST_INSPECTION_CRITICAL_VEHICLE_EVENT" in src
    assert "event_type IN ('DEFECT','BREAKDOWN')" in src
    assert "UPPER(severity) IN ('HIGH','CRITICAL')" in src


def test_driver_registry_v13_contains_runtime_vehicle_and_alert_codes():
    src = (ROOT / "ugatu" / "registry_driver_v1_3.json").read_text()
    for code in ("U-1910", "U-1920", "U-1950", "U-1960", "U-1970", "U-1980", "U-2020", "U-2040", "U-2050", "U-2060", "U-2070", "U-2080", "U-2280", "U-2290"):
        assert code in src
    loader = (ROOT / "ugatu" / "ugatu_registry.py").read_text()
    assert "registry_driver_v1_3.json" in loader
    assert "merged.extend" in loader


def test_secure_offline_finalization_is_mounted_and_blocks_route_close():
    entry = (ROOT / "ugatu_production_entrypoint.py").read_text()
    addon = (ROOT / "assets" / "driver-ugatu-finalize-v1.js").read_text()
    assert "/assets/driver-ugatu-finalize-v1.js" in entry
    assert "driver_secure_offline_finalization" in entry
    assert "UGATUOffline" in addon
    assert "completeRouteBtn" in addon
    assert "Route close blocked" in addon
    assert "ugatuConflictBtn" in addon
    assert "Encrypted IndexedDB queue active" in addon


def test_finalization_status_versions_are_exposed():
    src = (ROOT / "ugatu_production_entrypoint.py").read_text()
    assert '"driver_readiness_gate": "1.1.0"' in src
    assert '"driver_registry": "1.3.0"' in src
    assert '"driver_live_ugamap_routing": "1.1.0"' in src

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_sequence_policy_and_eta_markers():
    src = (ROOT / "ugatu" / "ugatu_driver_dashboard.py").read_text(encoding="utf-8")
    for marker in [
        "ACTIVE_WORK > URGENT > DUE_WINDOW > PROXIMITY",
        "distance_km_straight_line",
        "eta_confidence",
        "navigation_destination",
        "delivery_grid_id",
        "initial_next_stop_id",
    ]:
        assert marker in src


def test_ipad_sequence_addon_is_mounted():
    entry = (ROOT / "ugatu_production_entrypoint.py").read_text(encoding="utf-8")
    addon = (ROOT / "assets" / "driver-ugatu-sequence-v1.js").read_text(encoding="utf-8")
    dash = (ROOT / "assets" / "driver-ugatu-dashboard-v1.js").read_text(encoding="utf-8")
    assert "/assets/driver-ugatu-sequence-v1.js" in entry
    assert "driver_next_stop_sequencing" in entry
    assert "ugatu:dashboard-refreshed" in addon
    assert "priority_reason" in addon
    assert "ROUTE SEQUENCE" in dash
    assert "Drive estimate" in dash
    assert "navigation_destination" in dash

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_routing_backend_uses_ugamap_core():
    src = (ROOT / "ugatu" / "ugatu_driver_routing.py").read_text()
    assert 'from ugamap_core import core_address, core_route' in src
    assert 'mode="driving"' in src
    assert 'UGAMAP Core / Valhalla' in src
    assert 'ACTIVE_WORK > URGENT > DUE_WINDOW > UGAMAP_ROAD_TIME' in src
    assert 'CACHE_TTL_S = 90' in src
    assert 'MAX_ROUTED_STOPS = 12' in src


def test_live_routing_requires_driver_auth_and_location():
    src = (ROOT / "ugatu" / "ugatu_driver_routing.py").read_text()
    assert 'Driver passcode required' in src
    assert 'Invalid driver passcode' in src
    assert 'DRIVER_LOCATION_REQUIRED' in src
    assert 'current_lat' in src and 'current_lon' in src


def test_delivery_grid_is_resolved_before_road_route():
    src = (ROOT / "ugatu" / "ugatu_driver_routing.py").read_text()
    assert 'core_address(grid_id)' in src
    assert 'delivery_grid_id' in src
    assert 'navigation_destination' in src


def test_driver_ipad_mounts_live_routing_after_dashboard():
    src = (ROOT / "ugatu_production_entrypoint.py").read_text()
    assert 'ugatu_driver_routing_router' in src
    assert 'driver_routing_router_mounted' in src
    assert '/api/ugatu/driver-routing' in src
    dash = src.index('/assets/driver-ugatu-dashboard-v1.js')
    live = src.index('/assets/driver-ugatu-routing-v1.js')
    assert dash < live


def test_routing_addon_replaces_fallback_eta_and_recommends_live_sequence():
    src = (ROOT / "assets" / "driver-ugatu-routing-v1.js").read_text()
    assert '/api/ugatu/driver-routing' in src
    assert 'UGAMAP live route' in src
    assert 'road_distance_km' in src
    assert "routing_source:'UGAMAP_LIVE'" in src
    assert 'stopImmediatePropagation' in src

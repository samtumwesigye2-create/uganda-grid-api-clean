from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_leg_lifecycle_script_is_loaded_before_driver_core():
    entry = (ROOT / 'ugatu_production_entrypoint.py').read_text(encoding='utf-8')
    leg = '<script src="/assets/driver-ugatu-leg-v1.js"></script>'
    core = '<script src="/assets/driver-ugatu-v3.js"></script>'
    assert leg in entry
    assert entry.index('leg =') < entry.index('core =')
    assert 'html.replace(core, leg + core)' in entry


def test_pickup_to_delivery_bridge_preserves_legal_dispatch_transition():
    js = (ROOT / 'assets' / 'driver-ugatu-leg-v1.js').read_text(encoding='utf-8')
    assert "DELIVERY_STATUSES = new Set(['picked_up','en_route_dropoff','arrived_dropoff'])" in js
    assert "task_type: 'dropoff_customer'" in js
    assert "status: String(task.status).toLowerCase() === 'picked_up' ? 'en_route_dropoff'" in js
    assert "transition.append('status', 'en_route_dropoff')" in js
    assert "body.get('status') !== 'arrived_dropoff'" in js


def test_pure_pickup_marker_is_not_forced_into_delivery():
    js = (ROOT / 'assets' / 'driver-ugatu-leg-v1.js').read_text(encoding='utf-8')
    assert "notes.includes('pickup_only')" in js
    assert "return Boolean(task.shipment_number)" in js


def test_delivery_leg_navigation_does_not_reuse_pickup_coordinates():
    js = (ROOT / 'assets' / 'driver-ugatu-leg-v1.js').read_text(encoding='utf-8')
    assert "location_text: order.delivery_address || shipment.delivery || row.location_text" in js
    assert "delivery_grid_id: order.delivery_grid_id || row.delivery_grid_id || ''" in js
    assert 'latitude: null' in js
    assert 'longitude: null' in js

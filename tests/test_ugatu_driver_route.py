from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_includes_route_addon():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert '/assets/driver-ugatu-route-v1.js' in response.text


def test_route_addon_exposes_start_manifest_pickup_close_and_ledger():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-route-v1.js')
    assert response.status_code == 200
    for marker in [
        'START ROUTE', 'MANIFEST', 'ADD PICKUP', 'COMPLETE ROUTE',
        'U-1810', 'U-1860', 'U-1890',
        'ON VEHICLE', 'PICKUPS ADDED', 'DELIVERED', 'TRANSFERRED',
        'RETURNS', 'UNACCOUNTED', 'UNACCOUNTED must equal 0'
    ]:
        assert marker in response.text


def test_driver_route_endpoints_require_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-route/manifest').status_code == 401
    assert client.get('/api/ugatu/driver-route/ledger').status_code == 401
    assert client.post('/api/ugatu/driver-route/complete-route', json={}).status_code == 401


def test_dynamic_pickup_endpoint_requires_driver_auth():
    client = TestClient(app)
    response = client.post('/api/ugatu/driver-route/dynamic-pickup', json={
        'client_request_id': 'TEST-DYNAMIC-1',
        'location_text': 'Test Pickup Location'
    })
    assert response.status_code == 401


def test_complete_route_code_has_explicit_custody_block():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-route-v1.js')
    assert 'unaccounted_count' in response.text
    assert 'ROUTE CLOSE BLOCKED' in response.text
    assert 'UNACCOUNTED = 0' in response.text

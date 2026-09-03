from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_includes_dashboard_addon():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert '/assets/driver-ugatu-dashboard-v1.js' in response.text


def test_dashboard_addon_exposes_readiness_shift_and_next_stop():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-dashboard-v1.js')
    assert response.status_code == 200
    for marker in [
        'READY TO START ROUTE', 'ROUTE START BLOCKED', 'START SHIFT', 'END SHIFT',
        'NEXT STOP', 'PRE_TRIP_REQUIRED', '/api/ugatu/driver-dashboard/route/start'
    ]:
        assert marker in response.text


def test_dashboard_endpoints_require_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-dashboard').status_code == 401
    assert client.post('/api/ugatu/driver-dashboard/shift/start').status_code == 401
    assert client.post('/api/ugatu/driver-dashboard/shift/end').status_code == 401
    assert client.post('/api/ugatu/driver-dashboard/route/start', json={
        'client_request_id': 'TEST-ROUTE-GATE', 'device_id': 'TEST-IPAD'
    }).status_code == 401


def test_integration_status_reports_dashboard_router():
    client = TestClient(app)
    out = client.get('/api/ugatu/integration-status').json()
    assert out['driver_dashboard_router_mounted'] is True
    assert out['driver_dashboard'] == '/api/ugatu/driver-dashboard'

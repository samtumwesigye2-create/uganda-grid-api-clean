from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_includes_tasks_addon():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert '/assets/driver-ugatu-tasks-v1.js' in response.text


def test_tasks_asset_contains_core_alert_ucodes_and_actions():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-tasks-v1.js')
    assert response.status_code == 200
    for marker in [
        'Tasks & Alerts', 'UNREAD', 'URGENT', 'OPEN ACTION', 'NAVIGATE',
        '/api/ugatu/driver-center'
    ]:
        assert marker in response.text


def test_driver_center_requires_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-center').status_code == 401
    assert client.post('/api/ugatu/driver-center/assignment:test/read', json={}).status_code == 401


def test_integration_status_reports_driver_center():
    client = TestClient(app)
    response = client.get('/api/ugatu/integration-status')
    assert response.status_code == 200
    assert response.json()['driver_center_router_mounted'] is True

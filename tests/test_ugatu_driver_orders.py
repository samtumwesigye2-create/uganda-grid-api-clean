from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_orders_api_requires_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-orders').status_code == 401


def test_driver_orders_detail_requires_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-orders/not-a-task').status_code == 401


def test_driver_screen_loads_orders_addon():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert '/assets/driver-ugatu-orders-v1.js' in response.text


def test_driver_orders_addon_has_touch_actions():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-orders-v1.js')
    assert response.status_code == 200
    for marker in [
        'My Orders', 'PICKUPS', 'DELIVERIES', 'OPEN ORDER',
        'NAVIGATE', 'SCAN', 'DOCUMENTS', 'REPORT ISSUE',
        '/api/ugatu/driver-orders'
    ]:
        assert marker in response.text


def test_integration_status_reports_driver_orders_router():
    client = TestClient(app)
    response = client.get('/api/ugatu/integration-status')
    assert response.status_code == 200
    assert response.json()['driver_orders_router_mounted'] is True

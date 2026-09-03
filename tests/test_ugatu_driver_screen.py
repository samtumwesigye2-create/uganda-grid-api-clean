from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_ugatu_screen_loads():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert 'UGATU Driver' in response.text
    assert 'SCAN' in response.text
    assert '/assets/driver-ugatu-v1.js' in response.text


def test_driver_ugatu_asset_loads():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-v1.js')
    assert response.status_code == 200
    assert 'U-1550' in response.text
    assert 'U-1560' in response.text
    assert 'U-1570' in response.text

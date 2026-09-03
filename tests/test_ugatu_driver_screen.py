from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_ugatu_screen_loads():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert 'UGATU Driver' in response.text
    assert 'SCAN' in response.text
    assert 'DOCUMENTS' in response.text
    assert 'REPORT ISSUE' in response.text
    assert '/assets/driver-ugatu-v2.js' in response.text


def test_driver_ugatu_asset_loads():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-v2.js')
    assert response.status_code == 200
    assert 'U-1550' in response.text
    assert 'U-1560' in response.text
    assert 'U-1570' in response.text
    assert 'U-1600' in response.text
    assert 'U-1310' in response.text
    assert 'U-1320' in response.text


def test_driver_scan_is_bound_to_selected_stop():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-v2.js')
    assert 'Select an active stop before scanning.' in response.text
    assert 'does not match the selected stop' in response.text
    assert 'Change stop instead of forcing' in response.text


def test_driver_document_links_are_present():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert 'Bill of Lading' in response.text
    assert 'Receipt / Proof Document' in response.text

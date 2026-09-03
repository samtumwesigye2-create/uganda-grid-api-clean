from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_ugatu_screen_loads():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert 'UGATU Driver' in response.text
    assert 'ARRIVE' in response.text
    assert 'WORK STOP' in response.text
    assert 'COMPLETE STOP' in response.text
    assert 'SCAN' in response.text
    assert 'DOCUMENTS' in response.text
    assert 'REPORT ISSUE' in response.text
    assert '/assets/driver-ugatu-v3.js' in response.text


def test_driver_ugatu_asset_loads():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-v3.js')
    assert response.status_code == 200
    assert 'U-1830' in response.text
    assert 'U-1840' in response.text
    assert 'U-1550' in response.text
    assert 'U-1560' in response.text
    assert 'U-1570' in response.text
    assert 'U-1630' in response.text
    assert 'U-1640' in response.text
    assert 'U-1600' in response.text
    assert 'U-1310' in response.text
    assert 'U-1320' in response.text


def test_driver_scan_is_bound_to_selected_stop():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-v3.js')
    assert 'Select an active stop before scanning.' in response.text
    assert 'does not match the selected stop' in response.text
    assert 'Change stop instead of forcing' in response.text
    assert 'Record ARRIVE before scanning freight' in response.text
    assert 'Tap WORK STOP before scanning freight' in response.text


def test_driver_stop_completion_requires_proof_and_advances():
    client = TestClient(app)
    screen = client.get('/driver/ugatu')
    asset = client.get('/assets/driver-ugatu-v3.js')
    assert 'Proof Photo' in screen.text
    assert 'SAVE PROOF & COMPLETE' in screen.text
    assert 'Take a proof photo before completing this stop.' in asset.text
    assert 'Next stop selected:' in asset.text
    assert "proofUCode(t)" in asset.text


def test_driver_document_links_are_present():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert 'Bill of Lading' in response.text
    assert 'Receipt / Proof Document' in response.text

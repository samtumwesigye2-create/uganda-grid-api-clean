from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_includes_document_addon():
    client = TestClient(app)
    r = client.get('/driver/ugatu')
    assert r.status_code == 200
    assert '/assets/driver-ugatu-documents-v1.js' in r.text


def test_driver_document_routes_require_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-documents/task/not-a-task').status_code == 401
    assert client.get('/api/ugatu/driver-documents/DOC-NOPE/download').status_code == 401


def test_document_addon_uses_existing_business_documents_and_offline_cache():
    client = TestClient(app)
    r = client.get('/assets/driver-ugatu-documents-v1.js')
    assert r.status_code == 200
    for marker in [
        '/business-documents/bill-of-lading.html',
        '/business-documents/receipt.html',
        'indexedDB.open',
        'SAVE OFFLINE',
        'SAVE TO SHIPMENT',
        '/api/ugatu/driver-documents/task/'
    ]:
        assert marker in r.text


def test_existing_business_document_templates_exist():
    client = TestClient(app)
    assert client.get('/business-documents/bill-of-lading.html').status_code == 200
    assert client.get('/business-documents/receipt.html').status_code == 200

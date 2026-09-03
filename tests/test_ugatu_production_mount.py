from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_existing_health_still_works():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_ugatu_health_is_mounted():
    client = TestClient(app)
    response = client.get("/api/ugatu/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["codes"] > 0


def test_ugatu_integration_status():
    client = TestClient(app)
    response = client.get("/api/ugatu/integration-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ugatu_router_mounted"] is True
    assert payload["existing_app_preserved"] is True

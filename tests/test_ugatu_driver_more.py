from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_includes_more_addons():
    client = TestClient(app)
    response = client.get('/driver/ugatu')
    assert response.status_code == 200
    assert '/assets/driver-ugatu-more-v1.js' in response.text
    assert '/assets/driver-ugatu-more-energy-v1.js' in response.text


def test_more_addon_exposes_driver_operations():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-more-v1.js')
    assert response.status_code == 200
    for marker in [
        'PRE-TRIP', 'POST-TRIP', 'FUEL / CHARGE', 'REPORT DEFECT',
        'BREAKDOWN HELP', 'RETURNS', 'DISPATCH HISTORY',
        'SEARCH / FAVORITES', 'OFFLINE / SYNC', 'DRIVER PROFILE',
        'U-1920', 'U-1950', 'U-1960', 'U-1970', 'U-1980'
    ]:
        assert marker in response.text


def test_energy_mode_supports_fuel_charge_and_odometer():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-more-energy-v1.js')
    assert response.status_code == 200
    for marker in ['FUEL', 'CHARGE', 'ODOMETER', 'EV CHARGE']:
        assert marker in response.text


def test_driver_more_endpoints_require_driver_auth():
    client = TestClient(app)
    assert client.get('/api/ugatu/driver-more').status_code == 401
    assert client.get('/api/ugatu/driver-more/history').status_code == 401
    response = client.post('/api/ugatu/driver-more/vehicle-event', json={
        'event_type': 'PRE_TRIP',
        'notes': 'test'
    })
    assert response.status_code == 401


def test_vehicle_event_code_has_safety_out_of_service_guard():
    client = TestClient(app)
    response = client.get('/assets/driver-ugatu-more-v1.js')
    assert 'Take vehicle out of service' in response.text
    source = client.get('/driver/ugatu').text
    assert 'MORE' in source

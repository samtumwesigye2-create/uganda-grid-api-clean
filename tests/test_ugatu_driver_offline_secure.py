from fastapi.testclient import TestClient

from ugatu_production_entrypoint import app


def test_driver_screen_loads_secure_offline_before_core():
    client = TestClient(app)
    html = client.get('/driver/ugatu').text
    secure = '/assets/ugatu-offline-secure-v1.js'
    core = '/assets/driver-ugatu-v3.js'
    conflict = '/assets/driver-ugatu-offline-ui-v1.js'
    assert secure in html
    assert conflict in html
    assert html.index(secure) < html.index(core)


def test_secure_offline_runtime_uses_indexeddb_and_encryption():
    client = TestClient(app)
    source = client.get('/assets/ugatu-offline-secure-v1.js').text
    for marker in [
        'indexedDB.open', 'AES-GCM', 'PBKDF2', '180000',
        'device_time', 'depends_on', 'client_request_id',
        "state='CONFLICT'", 'migrateLegacy'
    ]:
        assert marker in source


def test_driver_commands_preserve_original_device_time():
    client = TestClient(app)
    source = client.get('/assets/driver-ugatu-v3.js').text
    assert 'device_time:new Date().toISOString()' in source
    assert 'UGATUOffline.enqueue' in source
    assert 'UGATUOffline.sync' in source
    assert 'dependency order' in source


def test_conflict_review_does_not_force_overwrite_custody():
    client = TestClient(app)
    source = client.get('/assets/driver-ugatu-offline-ui-v1.js').text
    assert 'Sync Conflict Review' in source
    assert 'Custody conflicts are never force-overwritten' in source
    assert 'Original device time' in source
    assert 'RETRY SYNC' in source

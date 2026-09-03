from fastapi.testclient import TestClient
import vector5250_entrypoint as v

client = TestClient(v.app)


def _identity(code, write=False):
    return {'id': 'TEST', 'name': 'Test Operator', 'role': 'SUPERVISOR', 'permissions': ['inventory:read','inventory:write']}


def test_vector5250_status_declares_independent_system_of_record():
    r = client.get('/api/vector5250/status')
    assert r.status_code == 200
    body = r.json()
    assert body['system'] == 'Vector 5250'
    assert body['phase'] == 2
    assert body['mode'] == 'independent-integrated'
    assert body['system_of_record'] == 'Vector 5250'
    assert body['relay_monitoring'] is True
    assert body['backup_replication'] is True
    assert body['ugatu_registry_modified'] is False


def test_vector5250_ui_has_no_seed_quick_login():
    r = client.get('/vector5250')
    assert r.status_code == 200
    html = r.text
    assert 'VECTOR 5250' in html
    assert 'INDEPENDENT ENTERPRISE SYSTEM OF RECORD' in html
    assert 'quickLogin' not in html
    assert 'ADMIN01' not in html
    assert '9999' not in html


def test_vector_command_stays_vector_native(monkeypatch):
    monkeypatch.setattr(v, '_identity', _identity)
    monkeypatch.setattr(v, '_record_event', lambda *a, **k: 'VEC-TEST')
    r = client.get('/api/vector5250/resolve/MIGO', headers={'x-access-code': 'test'})
    assert r.status_code == 200
    body = r.json()
    assert body['canonical'] == 'VECTOR5250'
    assert body['command'] == 'MIGO'
    assert 'U-4030' in body['ugatu_interop']


def test_unknown_vector_command_is_not_invented(monkeypatch):
    monkeypatch.setattr(v, '_identity', _identity)
    r = client.get('/api/vector5250/resolve/NOTREAL', headers={'x-access-code': 'test'})
    assert r.status_code == 404


def test_receiving_updates_vector_inventory_and_custody(monkeypatch, tmp_path):
    old = v.DB_PATH
    v.DB_PATH = tmp_path / 'vector5250-test.db'
    v._init_db()
    monkeypatch.setattr(v, '_identity', _identity)
    monkeypatch.setattr(v, 'relay_emit', lambda *a, **k: None)
    monkeypatch.setattr(v, 'vector5250_backup', lambda *a, **k: None)
    try:
        payload = {'reference':'PO-100','warehouse_id':'KLA-01','sku':'SKU-001','quantity':3,'unit_type':'package','location':'A-01','condition':'good','client_request_id':'REQ-1'}
        r = client.post('/api/vector5250/receiving', json=payload, headers={'x-access-code':'test'})
        assert r.status_code == 200
        body = r.json()
        assert body['status'] == 'RECEIVED'
        assert body['replayed'] is False
        c = v._db()
        try:
            qty = c.execute("SELECT quantity FROM vector_inventory WHERE warehouse_id='KLA-01' AND sku='SKU-001'").fetchone()['quantity']
            custody = c.execute("SELECT state FROM vector_custody WHERE object_code='SKU-001'").fetchone()['state']
        finally:
            c.close()
        assert qty == 3
        assert custody == 'IN_CUSTODY'
        replay = client.post('/api/vector5250/receiving', json=payload, headers={'x-access-code':'test'})
        assert replay.status_code == 200
        assert replay.json()['replayed'] is True
    finally:
        v.DB_PATH = old


def test_scan_is_vector_transaction(monkeypatch, tmp_path):
    old = v.DB_PATH
    v.DB_PATH = tmp_path / 'vector5250-scan.db'
    v._init_db()
    monkeypatch.setattr(v, '_identity', _identity)
    monkeypatch.setattr(v, 'relay_emit', lambda *a, **k: None)
    monkeypatch.setattr(v, 'vector5250_backup', lambda *a, **k: None)
    try:
        r = client.post('/api/vector5250/scan', json={'code':'PKG-100','warehouse_id':'KLA-01','scan_type':'package','action':'receive','client_request_id':'SCAN-1'}, headers={'x-access-code':'test'})
        assert r.status_code == 200
        assert r.json()['status'] == 'RECORDED'
    finally:
        v.DB_PATH = old


def test_backup_status_endpoint(monkeypatch):
    monkeypatch.setattr(v, '_identity', _identity)
    monkeypatch.setattr(v, 'sync_client_status', lambda: {'VECTOR5250': {'completed': 2, 'failed': 0}, 'queued': 0, 'active': 0, 'completed': 2, 'failed': 0, 'dropped': 0, 'last_attempt': 'x', 'last_success': 'x', 'last_error': None})
    r = client.get('/api/vector5250/backup-status', headers={'x-access-code':'test'})
    assert r.status_code == 200
    assert r.json()['status']['completed'] == 2

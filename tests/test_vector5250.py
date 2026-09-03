from fastapi.testclient import TestClient
import vector5250_entrypoint as v

client = TestClient(v.app)


def test_vector5250_status_declares_independent_system_of_record():
    r = client.get('/api/vector5250/status')
    assert r.status_code == 200
    body = r.json()
    assert body['system'] == 'Vector 5250'
    assert body['mode'] == 'independent-integrated'
    assert body['system_of_record'] == 'Vector 5250'
    assert body['relay_monitoring'] is True
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
    monkeypatch.setattr(v, '_identity', lambda code: {'id': 'TEST', 'role': 'OPERATOR'})
    monkeypatch.setattr(v, '_record_event', lambda *a, **k: 'VEC-TEST')
    r = client.get('/api/vector5250/resolve/MIGO', headers={'x-access-code': 'test'})
    assert r.status_code == 200
    body = r.json()
    assert body['canonical'] == 'VECTOR5250'
    assert body['command'] == 'MIGO'
    assert 'U-4030' in body['ugatu_interop']


def test_unknown_vector_command_is_not_invented(monkeypatch):
    monkeypatch.setattr(v, '_identity', lambda code: {'id': 'TEST', 'role': 'OPERATOR'})
    r = client.get('/api/vector5250/resolve/NOTREAL', headers={'x-access-code': 'test'})
    assert r.status_code == 404

from fastapi.testclient import TestClient
import vector5250_entrypoint as v

client = TestClient(v.app)


def test_vector5250_status_declares_shared_truth():
    r = client.get('/api/vector5250/status')
    assert r.status_code == 200
    body = r.json()
    assert body['system'] == 'Vector 5250'
    assert body['mode'] == 'integrated'
    assert 'UGASHIP/Warehouse' in body['system_of_record']
    assert body['commands'].startswith('UGATU')


def test_vector5250_ui_has_no_seed_quick_login():
    r = client.get('/vector5250')
    assert r.status_code == 200
    html = r.text
    assert 'VECTOR 5250' in html
    assert 'quickLogin' not in html
    assert 'ADMIN01' not in html
    assert '9999' not in html


def test_vector_alias_resolves_to_ugatu(monkeypatch):
    monkeypatch.setattr(v, '_identity', lambda code: {'id': 'TEST', 'role': 'OPERATOR'})
    r = client.get('/api/vector5250/resolve/MIGO', headers={'x-access-code': 'test'})
    assert r.status_code == 200
    body = r.json()
    assert body['canonical'] == 'UGATU'
    assert 'U-4030' in body['ugatu']


def test_unknown_vector_alias_is_not_invented(monkeypatch):
    monkeypatch.setattr(v, '_identity', lambda code: {'id': 'TEST', 'role': 'OPERATOR'})
    r = client.get('/api/vector5250/resolve/NOTREAL', headers={'x-access-code': 'test'})
    assert r.status_code == 404

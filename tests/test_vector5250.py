from fastapi.testclient import TestClient
import vector5250_entrypoint as v

client = TestClient(v.app)


def _identity(code, write=False):
    return {'id':'TEST','name':'Test Operator','role':'SUPERVISOR','permissions':['inventory:read','inventory:write']}


def _isolate(monkeypatch, tmp_path, name='vector5250-test.db'):
    old=v.DB_PATH
    v.DB_PATH=tmp_path/name
    v._init_db()
    monkeypatch.setattr(v,'_identity',_identity)
    monkeypatch.setattr(v,'relay_emit',lambda *a,**k:None)
    monkeypatch.setattr(v,'vector5250_backup',lambda *a,**k:None)
    return old


def test_vector5250_status_declares_independent_system_of_record():
    r=client.get('/api/vector5250/status')
    assert r.status_code==200
    body=r.json()
    assert body['system']=='Vector 5250'
    assert body['phase']==3
    assert body['mode']=='independent-integrated'
    assert body['system_of_record']=='Vector 5250'
    assert body['relay_monitoring'] is True
    assert body['backup_replication'] is True
    assert body['ugatu_registry_modified'] is False


def test_vector5250_ui_has_no_seed_quick_login():
    r=client.get('/vector5250')
    assert r.status_code==200
    html=r.text
    assert 'VECTOR 5250' in html
    assert 'INDEPENDENT ENTERPRISE SYSTEM OF RECORD' in html
    assert 'quickLogin' not in html
    assert 'ADMIN01' not in html
    assert '9999' not in html


def test_vector_command_stays_vector_native(monkeypatch):
    monkeypatch.setattr(v,'_identity',_identity)
    monkeypatch.setattr(v,'_record_event',lambda *a,**k:'VEC-TEST')
    r=client.get('/api/vector5250/resolve/MIGO',headers={'x-access-code':'test'})
    assert r.status_code==200
    body=r.json()
    assert body['canonical']=='VECTOR5250'
    assert body['command']=='MIGO'
    assert 'U-4030' in body['ugatu_interop']


def test_unknown_vector_command_is_not_invented(monkeypatch):
    monkeypatch.setattr(v,'_identity',_identity)
    assert client.get('/api/vector5250/resolve/NOTREAL',headers={'x-access-code':'test'}).status_code==404


def test_receiving_updates_vector_inventory_and_custody(monkeypatch,tmp_path):
    old=_isolate(monkeypatch,tmp_path)
    try:
        payload={'reference':'PO-100','warehouse_id':'KLA-01','sku':'SKU-001','quantity':3,'unit_type':'package','location':'A-01','condition':'good','client_request_id':'REQ-1'}
        r=client.post('/api/vector5250/receiving',json=payload,headers={'x-access-code':'test'})
        assert r.status_code==200 and r.json()['status']=='RECEIVED'
        c=v._db()
        try:
            assert c.execute("SELECT quantity FROM vector_inventory WHERE warehouse_id='KLA-01' AND sku='SKU-001'").fetchone()['quantity']==3
            assert c.execute("SELECT state FROM vector_custody WHERE object_code='SKU-001'").fetchone()['state']=='IN_CUSTODY'
            assert c.execute("SELECT quantity FROM vector_inventory_locations WHERE warehouse_id='KLA-01' AND sku='SKU-001' AND location='A-01'").fetchone()['quantity']==3
        finally:c.close()
        assert client.post('/api/vector5250/receiving',json=payload,headers={'x-access-code':'test'}).json()['replayed'] is True
    finally:v.DB_PATH=old


def test_scan_is_vector_transaction(monkeypatch,tmp_path):
    old=_isolate(monkeypatch,tmp_path,'scan.db')
    try:
        r=client.post('/api/vector5250/scan',json={'code':'PKG-100','warehouse_id':'KLA-01','scan_type':'package','action':'receive','client_request_id':'SCAN-1'},headers={'x-access-code':'test'})
        assert r.status_code==200 and r.json()['status']=='RECORDED'
    finally:v.DB_PATH=old


def test_phase3_inventory_move_and_history(monkeypatch,tmp_path):
    old=_isolate(monkeypatch,tmp_path,'move.db')
    try:
        client.post('/api/vector5250/receiving',json={'reference':'PO-1','warehouse_id':'KLA-01','sku':'SKU-X','quantity':10,'unit_type':'package','location':'A-01'},headers={'x-access-code':'test'})
        r=client.post('/api/vector5250/inventory/move',json={'warehouse_id':'KLA-01','sku':'SKU-X','from_location':'A-01','to_location':'B-02','quantity':4,'client_request_id':'MOVE-1'},headers={'x-access-code':'test'})
        assert r.status_code==200 and r.json()['status']=='MOVED'
        inv=client.get('/api/vector5250/inventory?warehouse_id=KLA-01&sku=SKU-X',headers={'x-access-code':'test'}).json()['results'][0]
        loc={x['location']:x['quantity'] for x in inv['locations']}
        assert loc['A-01']==6 and loc['B-02']==4
        hist=client.get('/api/vector5250/inventory/SKU-X/movements?warehouse_id=KLA-01',headers={'x-access-code':'test'}).json()
        assert hist['count']>=2
    finally:v.DB_PATH=old


def test_phase3_cycle_count_records_variance_without_silent_adjustment(monkeypatch,tmp_path):
    old=_isolate(monkeypatch,tmp_path,'count.db')
    try:
        client.post('/api/vector5250/receiving',json={'reference':'PO-2','warehouse_id':'KLA-01','sku':'SKU-C','quantity':8,'unit_type':'package'},headers={'x-access-code':'test'})
        opened=client.post('/api/vector5250/cycle-counts',json={'warehouse_id':'KLA-01','sku':'SKU-C','client_request_id':'COUNT-OPEN'},headers={'x-access-code':'test'}).json()
        done=client.post('/api/vector5250/cycle-counts/complete',json={'count_id':opened['count_id'],'counted_quantity':7,'client_request_id':'COUNT-DONE'},headers={'x-access-code':'test'})
        assert done.status_code==200
        assert done.json()['variance']==-1
        assert done.json()['adjustment_required'] is True
        inv=client.get('/api/vector5250/inventory?warehouse_id=KLA-01&sku=SKU-C',headers={'x-access-code':'test'}).json()['results'][0]
        assert inv['quantity']==8
    finally:v.DB_PATH=old


def test_phase3_explicit_adjustment_and_hold(monkeypatch,tmp_path):
    old=_isolate(monkeypatch,tmp_path,'adjust.db')
    try:
        client.post('/api/vector5250/receiving',json={'reference':'PO-3','warehouse_id':'KLA-01','sku':'SKU-A','quantity':5,'unit_type':'package'},headers={'x-access-code':'test'})
        adj=client.post('/api/vector5250/inventory/adjust',json={'warehouse_id':'KLA-01','sku':'SKU-A','delta':-1,'reason':'approved count variance','client_request_id':'ADJ-1'},headers={'x-access-code':'test'})
        assert adj.status_code==200 and adj.json()['quantity']==4
        hold=client.post('/api/vector5250/inventory/hold',json={'warehouse_id':'KLA-01','sku':'SKU-A','action':'hold','reason':'quality review','client_request_id':'HOLD-1'},headers={'x-access-code':'test'})
        assert hold.status_code==200 and hold.json()['status']=='HELD'
        inv=client.get('/api/vector5250/inventory?warehouse_id=KLA-01&sku=SKU-A',headers={'x-access-code':'test'}).json()['results'][0]
        assert inv['held'] is True
    finally:v.DB_PATH=old


def test_backup_status_endpoint(monkeypatch):
    monkeypatch.setattr(v,'_identity',_identity)
    monkeypatch.setattr(v,'sync_client_status',lambda:{'VECTOR5250':{'completed':2,'failed':0},'queued':0,'active':0,'completed':2,'failed':0,'dropped':0,'last_attempt':'x','last_success':'x','last_error':None})
    r=client.get('/api/vector5250/backup-status',headers={'x-access-code':'test'})
    assert r.status_code==200 and r.json()['status']['completed']==2

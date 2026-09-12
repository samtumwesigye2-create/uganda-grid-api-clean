from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_runtime_supports_session_binding_and_secure_purge():
    source = (ROOT / 'assets' / 'ugatu-offline-secure-v1.js').read_text(encoding='utf-8')
    for marker in ['SESSION_KEY', 'bindSession', 'purge', 'clearStore', 'session_fingerprint']:
        assert marker in source


def test_driver_documents_record_access_and_upload_audit():
    source = (ROOT / 'ugatu' / 'ugatu_driver_documents.py').read_text(encoding='utf-8')
    for marker in ['ugatu_driver_document_audit', '_audit(', "'UPLOAD'", "'DOWNLOAD'"]:
        assert marker in source


def test_driver_lifecycle_exposes_shift_and_shipment_leg_controls():
    source = (ROOT / 'ugatu' / 'ugatu_driver_lifecycle.py').read_text(encoding='utf-8')
    for marker in ['ugatu_driver_shifts', 'ugatu_shipment_legs', '/shift/start', '/shift/reconcile', '/legs']:
        assert marker in source


def test_driver_frontend_binds_session_and_guards_secure_purge():
    source = (ROOT / 'assets' / 'driver-ugatu-finalize-v1.js').read_text(encoding='utf-8')
    assert 'bindSecureSession' in source
    assert 'api.bindSession' in source
    assert 'api.purge({force:false})' in source


def test_production_entrypoint_mounts_driver_lifecycle():
    source = (ROOT / 'ugatu_production_entrypoint.py').read_text(encoding='utf-8')
    assert 'ugatu_driver_lifecycle_router' in source
    assert "'/api/ugatu/driver-lifecycle'" in source

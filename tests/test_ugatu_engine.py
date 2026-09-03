from ugatu.ugatu_engine import UGATUEngine
from ugatu.ugatu_models import ExecuteRequest
from ugatu.ugatu_registry import registry


def test_resolve_pickup_alias_for_driver():
    item = registry.resolve("collect freight", role="DRIVER")
    assert item is not None
    assert item.ucode == "U-1550"


def test_role_visibility_blocks_billing_for_driver():
    assert registry.resolve("Generate Invoice", role="DRIVER") is None


def test_idempotency_prevents_duplicate_event():
    engine = UGATUEngine()
    request = ExecuteRequest(
        ucode="U-1550",
        parameters={"package_id": "PKG-1", "route_id": "RTE-1", "stop_id": "STP-1"},
        client_request_id="REQ-1",
        actor_id="DRV-1",
        role="DRIVER",
        device_id="IPAD-1",
    )
    first = engine.execute(request)
    second = engine.execute(request)
    assert first.transaction_id == second.transaction_id
    assert second.duplicate is True
    assert len(engine.events) == 1


def test_offline_policy_enforced():
    engine = UGATUEngine()
    request = ExecuteRequest(
        ucode="U-6050",
        parameters={"shipment_id": "SHP-1"},
        client_request_id="REQ-2",
        role="BILLING",
        offline=True,
    )
    try:
        engine.execute(request)
        assert False, "Expected ValueError"
    except ValueError:
        assert True

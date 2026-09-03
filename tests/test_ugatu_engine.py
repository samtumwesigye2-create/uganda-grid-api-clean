from ugatu.ugatu_context import resolve_scan_ucode
from ugatu.ugatu_engine import UGATUEngine
from ugatu.ugatu_models import ExecuteRequest
from ugatu.ugatu_registry import registry


def test_resolve_pickup_alias_for_driver():
    item = registry.resolve("collect freight", role="DRIVER")
    assert item is not None
    assert item.ucode == "U-1550"


def test_role_visibility_blocks_billing_for_driver():
    assert registry.resolve("Generate Invoice", role="DRIVER") is None


def test_driver_orders_are_visible():
    item = registry.resolve("My Orders", role="DRIVER")
    assert item is not None
    assert item.ucode == "U-5000"


def test_context_scan_resolves_pickup():
    assert resolve_scan_ucode({"stop_type": "PICKUP"}) == "U-1550"


def test_context_scan_resolves_delivery():
    assert resolve_scan_ucode({"stop_type": "DELIVERY"}) == "U-1560"


def test_context_scan_resolves_handoff():
    assert resolve_scan_ucode({"stop_type": "HANDOFF"}) == "U-1570"


def test_idempotency_prevents_duplicate_event():
    engine = UGATUEngine()
    request = ExecuteRequest(
        ucode="U-1550",
        parameters={"package_id": "PKG-1", "route_id": "RTE-1", "stop_id": "STP-1"},
        client_request_id="REQ-IDEMPOTENCY-1",
        actor_id="DRV-1",
        role="DRIVER",
        device_id="IPAD-1",
    )
    first = engine.execute(request)
    second = engine.execute(request)
    assert first.transaction_id == second.transaction_id
    assert second.duplicate is True


def test_pickup_requires_scanned_object():
    engine = UGATUEngine()
    request = ExecuteRequest(
        ucode="U-1550",
        parameters={"route_id": "RTE-1", "stop_id": "STP-1"},
        client_request_id="REQ-PICKUP-VALIDATION-1",
        actor_id="DRV-1",
        role="DRIVER",
    )
    try:
        engine.execute(request)
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_offline_policy_enforced():
    engine = UGATUEngine()
    request = ExecuteRequest(
        ucode="U-6050",
        parameters={"shipment_id": "SHP-1"},
        client_request_id="REQ-OFFLINE-2",
        role="BILLING",
        offline=True,
    )
    try:
        engine.execute(request)
        assert False, "Expected ValueError"
    except ValueError:
        assert True

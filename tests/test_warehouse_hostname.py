"""Regression coverage for warehouse subdomain dispatch without loading databases."""
import ast
import asyncio
from pathlib import Path


def invoke(host, path="/", method="GET"):
    source = Path("railway_entrypoint.py").read_text()
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "app")
    routed = []
    async def production(scope, receive, send):
        routed.append(scope)
    async def bridge(scope, receive):
        return None
    class Relay:
        def __call__(self, *args):
            pass
    import time
    namespace = dict(time=time, production_app=production, maybe_handle_zipper_bridge=bridge, relay_emit=Relay(), _public_index=lambda: "map")
    from fastapi.responses import Response
    namespace["Response"] = Response
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "railway_entrypoint.py", "exec"), namespace)
    async def receive():
        return {"type":"http.request", "body":b""}
    async def send(message):
        pass
    asyncio.run(namespace["app"]({"type":"http", "method":method, "path":path, "raw_path":path.encode(), "headers":[(b"host",host.encode())]}, receive, send))
    return routed


def test_warehouse_home_opens_warehouse():
    routed = invoke("warehouse.ugandagrid.com")
    assert routed, "Warehouse homepage incorrectly served the map"
    scope = routed[0]
    assert scope["path"] == "/warehouse"
    assert scope["raw_path"] == b"/warehouse"


def test_hostname_with_port_and_head():
    assert invoke("warehouse.ugandagrid.com:443", method="HEAD")[0]["path"] == "/warehouse"


def test_warehouse_api_paths_unchanged():
    assert invoke("warehouse.ugandagrid.com", "/warehouse/staff")[0]["path"] == "/warehouse/staff"


def test_other_hosts_keep_original_path():
    assert invoke("ugandagrid.com", "/warehouse")[0]["path"] == "/warehouse"

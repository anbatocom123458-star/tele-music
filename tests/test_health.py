"""/health endpoint contract (spec §24) — no secrets in response."""
from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from app.web.health import create_health_app


async def test_health_ok():
    app = create_health_app(lambda: True, lambda: _true())
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"status": "ok", "tts": True, "database": True}
    await client.close()


async def test_health_degraded():
    async def db_down():
        return False

    app = create_health_app(lambda: False, db_down)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    resp = await client.get("/health")
    assert resp.status == 503
    data = await resp.json()
    assert data["tts"] is False and data["database"] is False
    await client.close()


async def _true():
    return True

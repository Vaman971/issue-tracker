import pytest
from httpx import AsyncClient

import app.main as main_module


@pytest.mark.asyncio
async def test_liveness_check(client: AsyncClient):
    response = await client.get("/health/live")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "alive"
    assert data["environment"] == "test"


@pytest.mark.asyncio
async def test_readiness_check_success(client: AsyncClient):
    response = await client.get("/health/ready")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ready"
    assert data["database"] == "up"
    assert data["redis"] == "up"


@pytest.mark.asyncio
async def test_readiness_check_when_redis_is_down(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_ping_redis():
        return False

    monkeypatch.setattr(main_module, "ping_redis", fake_ping_redis)

    response = await client.get("/health/ready")

    assert response.status_code == 503

    data = response.json()

    assert data["status"] == "unready"
    assert data["database"] == "up"
    assert data["redis"] == "down"

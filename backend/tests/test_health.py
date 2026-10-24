import asyncio

from httpx import ASGITransport, AsyncClient, Response

from app.main import app



async def _get(path: str) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


def test_health_endpoint_reports_api_running() -> None:
    response = asyncio.run(_get("/api/v1/health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fdr-guardian-api"}


def test_database_health_reports_unconfigured_when_url_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = asyncio.run(_get("/api/v1/health/database"))

    assert response.status_code == 200
    assert response.json() == {"status": "not_configured"}

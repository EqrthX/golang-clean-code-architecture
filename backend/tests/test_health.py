from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.infrastructure.database import connector
from app.main import create_app


def test_health_contract_and_frontend_origin(monkeypatch):
    monkeypatch.setattr(connector, "check_database_connections", AsyncMock())
    settings = Settings(
        _env_file=None,
        name="Test API",
        postgres_db_password="test-only",
        secret_key="test-only-secret-key-with-32-characters",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "name": "Test API", "version": "0.1.0"}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

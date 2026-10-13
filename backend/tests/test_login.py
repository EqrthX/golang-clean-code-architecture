from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from app.infrastructure.database import connector
from app.interface.http.routes.auth import get_user_repository
from app.main import create_app
from app.usecases import usecease_auth


class FakeLoginRepository:
    def __init__(self, credentials):
        self.credentials = credentials
        self.sessions = []

    async def get_credentials_by_email(self, email):
        return self.credentials

    async def create_session(self, session_id, user_id, refresh_hash, expires_at):
        self.sessions.append((session_id, user_id, refresh_hash, expires_at))


@pytest.fixture(scope="module")
def password_hash():
    return bcrypt.hashpw(b"abcdefgh", bcrypt.gensalt()).decode()


@pytest.fixture
def login_client(monkeypatch, password_hash):
    monkeypatch.setattr(connector, "check_database_connections", AsyncMock())
    repository = FakeLoginRepository((7, password_hash))
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository


def test_login_returns_200_and_signed_token_with_configured_expiry(login_client, password_hash):
    client, _ = login_client
    before = datetime.now(timezone.utc).timestamp()
    response = client.post("/login", json={"email": "alice@example.com", "password": "abcdefgh"})
    after = datetime.now(timezone.utc).timestamp()
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "refresh_token", "token_type"}
    assert body["token_type"] == "bearer"
    claims = jwt.decode(
        body["access_token"],
        usecease_auth.config.secret_key.get_secret_value(),
        algorithms=["HS256"],
        options={"require": ["sub", "exp"]},
    )
    assert claims["sub"] == "7"
    lifetime = usecease_auth.config.jwt_access_expires * 60
    assert before + lifetime - 1 <= claims["exp"] <= after + lifetime
    assert set(claims) == {"sub", "exp", "sid", "type"}
    assert claims["type"] == "access"
    refresh_claims = jwt.decode(
        body["refresh_token"],
        usecease_auth.config.secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    assert refresh_claims["type"] == "refresh"
    assert refresh_claims["sid"] == claims["sid"]
    assert refresh_claims["exp"] > claims["exp"]
    assert login_client[1].sessions[0][2] == usecease_auth.token_hash(body["refresh_token"])
    assert "abcdefgh" not in response.text
    assert password_hash not in response.text
    spec = client.get("/openapi.json").json()["paths"]["/login"]["post"]
    assert "application/json" in spec["requestBody"]["content"]
    assert "200" in spec["responses"]


def test_unknown_email_and_wrong_password_return_same_401(login_client):
    client, repository = login_client
    wrong = client.post("/login", json={"email": "alice@example.com", "password": "wrongpass"})
    repository.credentials = None
    missing = client.post("/login", json={"email": "missing@example.com", "password": "abcdefgh"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong.headers["www-authenticate"] == "Bearer"
    assert "access_token" not in wrong.json()


def test_invalid_stored_hash_does_not_issue_token(login_client):
    client, repository = login_client
    repository.credentials = (7, "invalid-hash")
    response = client.post("/login", json={"email": "alice@example.com", "password": "abcdefgh"})
    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": None, "password": "abcdefgh"},
        {"email": "alice@example.com", "password": None},
        {"email": "invalid", "password": "abcdefgh"},
        {"email": "alice@example.com", "password": ""},
        {"email": "alice@example.com", "password": "a" * 73},
        {"email": "alice@example.com", "password": "ก" * 25},
    ],
)
def test_login_rejects_invalid_input_before_repository(login_client, payload):
    client, repository = login_client
    repository.get_credentials_by_email = AsyncMock(side_effect=AssertionError("must not query"))
    response = client.post("/login", json=payload)
    assert response.status_code == 422
    repository.get_credentials_by_email.assert_not_awaited()
    assert all("input" not in error for error in response.json()["detail"])


def test_valid_thai_password_at_bcrypt_boundary(login_client):
    client, repository = login_client
    password = "ก" * 24
    repository.credentials = (8, bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    response = client.post("/login", json={"email": "thai@example.com", "password": password})
    assert response.status_code == 200


def test_repository_failure_is_not_swallowed_as_bad_credentials(monkeypatch):
    repository = FakeLoginRepository(None)
    repository.get_credentials_by_email = AsyncMock(side_effect=RuntimeError("DB unavailable"))
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/login", json={"email": "alice@example.com", "password": "abcdefgh"}
        )
    assert response.status_code == 500


@pytest.mark.parametrize("lifetime", [timedelta(0), timedelta(seconds=-1)])
def test_token_lifetime_must_be_positive(lifetime):
    with pytest.raises(ValueError, match="positive"):
        usecease_auth.create_access_token({"sub": "7"}, lifetime)


def test_token_custom_lifetime_and_input_is_not_mutated():
    data = {"sub": "7"}
    before = datetime.now(timezone.utc).timestamp()
    token = usecease_auth.create_access_token(data, timedelta(minutes=2))
    claims = jwt.decode(
        token, usecease_auth.config.secret_key.get_secret_value(), algorithms=["HS256"]
    )
    assert before + 119 <= claims["exp"] <= datetime.now(timezone.utc).timestamp() + 120
    assert data == {"sub": "7"}
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "different-test-key-with-at-least-32-bytes", algorithms=["HS256"])


def test_token_expiration_claim_is_enforced_by_decoder(monkeypatch):
    real_now = datetime.now(timezone.utc)

    class PastDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_now - timedelta(minutes=2)

    monkeypatch.setattr(usecease_auth, "datetime", PastDatetime)
    token = usecease_auth.create_access_token({"sub": "7"}, timedelta(seconds=1))
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, usecease_auth.config.secret_key.get_secret_value(), algorithms=["HS256"])

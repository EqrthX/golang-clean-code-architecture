import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from app.domain.entities.auth import UserSession
from app.domain.entities.user import User
from app.interface.http.dependencies import get_user_repository
from app.main import create_app
from app.usecases import usecease_auth as auth


class MemoryRepository:
    def __init__(self, password_hash):
        self.password_hash = password_hash
        self.user = User(id=7, name="Profile Tester", email="profile@example.com")
        self.sessions = {}
        self.permission = "user"

    async def get_credentials_by_email(self, email):
        return (7, self.password_hash) if email == self.user.email else None

    async def get_user_by_id(self, user_id):
        return self.user if user_id == 7 else None

    async def create_session(self, session_id, user_id, refresh_hash, expires_at):
        self.sessions[session_id] = UserSession(session_id, user_id, refresh_hash, expires_at)

    async def get_session(self, session_id, user_id):
        session = self.sessions.get(session_id)
        return session if session and session.user_id == user_id else None

    async def rotate_session(self, session_id, user_id, old_hash, new_hash):
        session = await self.get_session(session_id, user_id)
        if session is None or session.refresh_hash != old_hash:
            return False
        self.sessions[session_id] = replace(session, refresh_hash=new_hash)
        return True

    async def delete_session(self, session_id, user_id, refresh_hash):
        session = await self.get_session(session_id, user_id)
        if session is None or session.refresh_hash != refresh_hash:
            return False
        del self.sessions[session_id]
        return True

    async def get_permission(self, user_id):
        return self.permission

    async def list_records(self, resource, user_id, admin, page, page_size):
        self.last_list_args = (resource, user_id, admin, page, page_size)
        return [{"id": 7, "name": self.user.name, "email": self.user.email}], 1

    async def get_record(self, resource, record_id, user_id, admin):
        return {"id": 7} if record_id == "7" else None


@pytest.fixture(scope="module")
def password_hash():
    return bcrypt.hashpw(b"abcdefgh", bcrypt.gensalt()).decode()


@pytest.fixture
def client_and_repository(password_hash):
    repository = MemoryRepository(password_hash)
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository
    return TestClient(app), repository


def login(client):
    response = client.post("/login", json={"email": "profile@example.com", "password": "abcdefgh"})
    assert response.status_code == 200
    return response.json()


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_profile_is_public_dto_and_repository_returns_none_for_missing_user(client_and_repository):
    client, repository = client_and_repository
    tokens = login(client)
    repository.user.password = "private-password-marker"
    response = client.get("/profile", headers=bearer(tokens["access_token"]))
    assert response.status_code == 200
    assert set(response.json()) == {"id", "name", "email", "created_at", "updated_at"}
    assert response.json()["id"] == 7
    assert "private-password-marker" not in response.text
    assert (
        client.post("/api/v1/users/profile", headers=bearer(tokens["access_token"])).status_code
        == 200
    )
    repository.user = None
    assert client.get("/profile", headers=bearer(tokens["access_token"])).status_code == 401


@pytest.mark.parametrize("subject", ["abc", "", "0", "-1", "2147483648", "١"])
def test_invalid_user_id_claim_is_401(client_and_repository, subject):
    client, _ = client_and_repository
    token = auth.create_access_token({"sub": subject, "sid": str(uuid4()), "type": "access"})
    assert client.get("/profile", headers=bearer(token)).status_code == 401


def test_missing_expired_bad_signature_and_refresh_token_are_rejected(client_and_repository):
    client, _ = client_and_repository
    tokens = login(client)
    claims = jwt.decode(
        tokens["access_token"], auth.config.secret_key.get_secret_value(), algorithms=["HS256"]
    )
    claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired = jwt.encode(claims, auth.config.secret_key.get_secret_value(), algorithm="HS256")
    wrong = jwt.encode(
        {**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=1)},
        "test-key-with-more-than-32-characters",
        algorithm="HS256",
    )
    for token in [
        expired,
        wrong,
        "not-a-jwt",
        tokens["refresh_token"],
        auth.config.secret_key.get_secret_value(),
    ]:
        response = client.get("/profile", headers=bearer(token))
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
    assert client.get("/profile").status_code == 401


def test_refresh_rotates_once_preserves_session_expiry_and_logout_revokes_access(
    client_and_repository,
):
    client, repository = client_and_repository
    old = login(client)
    response = client.post("/refresh-token", json={"refresh_token": old["refresh_token"]})
    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]
    old_claims = auth.verify_token(old["refresh_token"], "refresh")
    new_claims = auth.verify_token(new["refresh_token"], "refresh")
    assert old_claims["exp"] == new_claims["exp"]
    assert len(repository.sessions) == 1
    assert (
        client.post("/refresh-token", json={"refresh_token": old["refresh_token"]}).status_code
        == 401
    )
    assert client.post("/logout", json={"refresh_token": old["refresh_token"]}).status_code == 401
    assert client.get("/profile", headers=bearer(new["access_token"])).status_code == 200
    assert client.post("/logout", json={"refresh_token": new["refresh_token"]}).status_code == 204
    assert client.get("/protected", headers=bearer(new["access_token"])).status_code == 401
    assert client.get("/profile", headers=bearer(old["access_token"])).status_code == 401
    assert (
        client.post("/refresh-token", json={"refresh_token": new["refresh_token"]}).status_code
        == 401
    )


def test_multiple_logins_have_independent_sessions(client_and_repository):
    client, _ = client_and_repository
    first, second = login(client), login(client)
    assert client.post("/logout", json={"refresh_token": first["refresh_token"]}).status_code == 204
    assert client.get("/profile", headers=bearer(second["access_token"])).status_code == 200


@pytest.mark.parametrize("path", ["/refresh-token", "/logout"])
def test_access_token_cannot_be_used_as_refresh_token(client_and_repository, path):
    client, _ = client_and_repository
    tokens = login(client)
    assert client.post(path, json={"refresh_token": tokens["access_token"]}).status_code == 401


def test_read_routes_require_auth_validate_pagination_and_pass_scope(client_and_repository):
    client, repository = client_and_repository
    assert client.get("/data/users/").status_code == 401
    tokens = login(client)
    headers = bearer(tokens["access_token"])
    response = client.get("/data/users/?_page=2&_pageSize=5", headers=headers)
    assert response.status_code == 200
    assert repository.last_list_args == ("users", 7, False, 2, 5)
    assert response.json()["total_data"] == 1
    repository.permission = "admin"
    client.get("/data/users/", headers=headers)
    assert repository.last_list_args[2] is True
    for query in ["_page=0", "_pageSize=0", "_pageSize=101"]:
        assert client.get("/data/users/?" + query, headers=headers).status_code == 422
    for resource in ["users", "user_permissions", "user_tokens"]:
        described = client.get(f"/data/{resource}/describe", headers=headers)
        assert described.status_code == 200
        assert "password" not in described.text and "refresh_hash" not in described.text
    assert client.get("/data/unknown/", headers=headers).status_code == 404
    assert client.get("/data/users/999", headers=headers).status_code == 404


def test_cors_allows_frontend_authorization_and_openapi_has_bearer_security(client_and_repository):
    client, _ = client_and_repository
    response = client.options(
        "/profile",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/profile"]["get"]["security"]
    assert spec["paths"]["/profile"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("UserRead")


def test_domain_and_usecases_do_not_import_http_or_orm():
    root = Path(__file__).resolve().parents[1] / "app"
    for layer in ["domain", "usecases"]:
        for path in (root / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                assert not any(name.startswith(("fastapi", "sqlalchemy")) for name in names), path

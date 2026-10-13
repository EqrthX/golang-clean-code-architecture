import asyncio
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import bcrypt
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.entities.user import User
from app.domain.errors import DuplicateEmailError
from app.infrastructure.database import connector
from app.infrastructure.database.models.user_model import UserSQLModel
from app.infrastructure.database.session import get_postgres_db
from app.infrastructure.database.user_repository import PostgresUserRepository, create_user
from app.interface.http.routes.auth import get_user_repository
from app.main import create_app
from app.usecases import usecease_auth


class FakeRepository:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.created = []

    async def check_user_exists(self, email):
        return 7 if self.duplicate else None

    async def create_user(self, name, email, password_hash):
        self.created.append(password_hash)
        return User(id=7, name=name, email=email)


@pytest.fixture
def http_client(monkeypatch):
    monkeypatch.setattr(connector, "check_database_connections", AsyncMock())
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository


def test_registration_json_and_safe_response(http_client):
    client, repository = http_client
    response = client.post(
        "/register",
        json={"name": " Alice ", "email": "alice@example.com", "password": "abcdefgh"},
    )
    assert response.status_code == 201
    assert response.json()["Register"] == "Success"
    assert response.json()["Data"]["name"] == "Alice"
    assert response.json()["Data"]["id"] == 7
    assert "password" not in response.json()["Data"]
    assert "abcdefgh" not in response.text
    assert repository.created[0] not in response.text
    assert bcrypt.checkpw(b"abcdefgh", repository.created[0].encode())
    spec = client.get("/openapi.json").json()["paths"]["/register"]["post"]
    assert "application/json" in spec["requestBody"]["content"]
    assert not spec.get("parameters")


def test_duplicate_email_does_not_hash_or_insert(http_client, monkeypatch):
    client, repository = http_client
    repository.duplicate = True
    hasher = MagicMock(side_effect=AssertionError("duplicate must not reach hashing"))
    monkeypatch.setattr(usecease_auth, "hashPassword", hasher)
    response = client.post(
        "/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "abcdefgh"},
    )
    assert response.status_code == 409
    hasher.assert_not_called()
    assert not repository.created


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "tiny123"},
        {"password": "a" * 73},
        {"password": "ก" * 25},
        {"email": "invalid"},
        {"name": "   "},
    ],
)
def test_invalid_registration_does_not_insert_or_echo_password(http_client, changes):
    client, repository = http_client
    payload = {"name": "Alice", "email": "alice@example.com", "password": "abcdefgh"}
    payload.update(changes)
    response = client.post("/register", json=payload)
    assert response.status_code == 422
    assert payload["password"] not in response.text
    assert not repository.created


def test_bcrypt_exact_byte_boundary(http_client):
    client, repository = http_client
    response = client.post(
        "/register", json={"name": "Alice", "email": "alice@example.com", "password": "ก" * 24}
    )
    assert response.status_code == 201
    assert bcrypt.checkpw(("ก" * 24).encode(), repository.created[0].encode())


@pytest.mark.parametrize("email_conflict", [True, False])
def test_integrity_error_rolls_back_and_only_email_conflict_is_translated(email_conflict):
    cause = Exception("database constraint violation")
    cause.constraint_name = "uq_users_email" if email_conflict else "other_constraint"
    original = Exception("database error")
    original.sqlstate = "23505"
    original.__cause__ = cause
    error = IntegrityError("INSERT", {}, original)
    session = MagicMock()
    session.flush = AsyncMock(side_effect=error)
    session.rollback = AsyncMock()
    session.commit = AsyncMock()

    async def run():
        expected = DuplicateEmailError if email_conflict else IntegrityError
        with pytest.raises(expected):
            await create_user(
                session, name="Alice", email="alice@example.com", password_hash="hash"
            )
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    asyncio.run(run())


def test_mapper_failure_rolls_back_before_commit(monkeypatch):
    session = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    from app.infrastructure.database import user_repository

    monkeypatch.setattr(
        user_repository.UserMapper, "to_entity", MagicMock(side_effect=ValueError("invalid entity"))
    )

    async def run():
        with pytest.raises(ValueError):
            await create_user(
                session, name="Alice", email="alice@example.com", password_hash="hash"
            )
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for Docker DB"
)
def test_registration_and_concurrent_duplicate_with_real_postgres():
    # UUID emails isolate test data; finally removes only these specific rows.
    email = f"register-{uuid4().hex}@example.com"
    race_email = f"race-{uuid4().hex}@example.com"

    async def run():
        engine = create_async_engine(connector.url_object, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app()

        async def test_session():
            async with factory() as session:
                yield session

        app.dependency_overrides[get_postgres_db] = test_session
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {"name": "Integration", "email": email, "password": "abcdefgh"}
                response = await client.post("/register", json=payload)
                assert response.status_code == 201, response.text
                assert (await client.post("/register", json=payload)).status_code == 409
                async with factory() as session:
                    stored = await session.scalar(
                        select(UserSQLModel).where(UserSQLModel.email == email)
                    )
                    assert bcrypt.checkpw(b"abcdefgh", stored.password.encode())
                    assert stored.password not in response.text
                    assert stored.name == "Integration"
                    assert response.json()["Data"]["id"] == stored.id

                login = await client.post("/login", json={"email": email, "password": "abcdefgh"})
                assert login.status_code == 200, login.text
                assert login.json()["token_type"] == "bearer"
                claims = jwt.decode(
                    login.json()["access_token"],
                    usecease_auth.config.secret_key.get_secret_value(),
                    algorithms=["HS256"],
                    options={"require": ["sub", "exp"]},
                )
                assert claims["sub"] == str(stored.id)
                assert stored.password not in login.text
                wrong = await client.post("/login", json={"email": email, "password": "wrongpass"})
                missing = await client.post(
                    "/login",
                    json={"email": f"missing-{uuid4().hex}@example.com", "password": "abcdefgh"},
                )
                assert wrong.status_code == missing.status_code == 401
                assert wrong.json() == missing.json()

            # Both sessions attempt INSERT; bypass the pre-check to exercise DB protection.
            async def concurrent_insert():
                async with factory() as session:
                    return await PostgresUserRepository(session).create_user(
                        name="Race", email=race_email, password_hash=stored.password
                    )

            outcomes = await asyncio.gather(
                concurrent_insert(), concurrent_insert(), return_exceptions=True
            )
            assert sum(isinstance(outcome, User) for outcome in outcomes) == 1
            assert sum(isinstance(outcome, DuplicateEmailError) for outcome in outcomes) == 1
            async with factory() as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(UserSQLModel)
                    .where(UserSQLModel.email == race_email)
                )
                assert count == 1
                assert await session.scalar(text("SELECT 1")) == 1
        finally:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(UserSQLModel).where(UserSQLModel.email.in_([email, race_email]))
                )
            await engine.dispose()

    asyncio.run(run())

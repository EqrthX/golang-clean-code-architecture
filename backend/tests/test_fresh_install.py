import asyncio
import os
import re
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.database import connector
from app.infrastructure.database.models.user_model import (
    Base,
    UserPermissionSQLModel,
    UserTokenSQLModel,
)
from app.infrastructure.database.session import get_postgres_db
from app.main import create_app
from app.usecases.usecease_auth import token_hash


@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 for PostgreSQL"
)
def test_fresh_migrations_permissions_refresh_race_logout_and_downgrade():
    # Only this newly generated schema is created/dropped; public user data is untouched.
    schema = "submission_test_" + uuid4().hex
    assert re.fullmatch(r"submission_test_[0-9a-f]{32}", schema)

    def migrate(connection, operation, revision):
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        operation(config, revision)

    async def run():
        admin_engine = create_async_engine(connector.url_object, poolclass=NullPool)
        engine = None
        created = False
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                created = True
            engine = create_async_engine(
                connector.url_object,
                poolclass=NullPool,
                connect_args={"server_settings": {"search_path": schema}},
            )
            async with engine.begin() as connection:
                await connection.run_sync(lambda conn: migrate(conn, command.upgrade, "head"))
                differences = await connection.run_sync(
                    lambda conn: compare_metadata(MigrationContext.configure(conn), Base.metadata)
                )
                assert differences == [], differences
            factory = async_sessionmaker(engine, expire_on_commit=False)

            async def test_session():
                async with factory() as session:
                    yield session

            app = create_app()
            app.dependency_overrides[get_postgres_db] = test_session
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                users = []
                tokens = []
                for name in ["Alice", "Bob"]:
                    email = f"{name.lower()}-{uuid4().hex}@example.com"
                    payload = {"name": name, "email": email, "password": "abcdefgh"}
                    response = await client.post("/register", json=payload)
                    assert response.status_code == 201, response.text
                    assert (await client.post("/register", json=payload)).status_code == 409
                    users.append(response.json()["Data"])
                    response = await client.post(
                        "/api/v1/users/login", json={"email": email, "password": "abcdefgh"}
                    )
                    assert response.status_code == 200, response.text
                    tokens.append(response.json())
                alice, bob = users
                alice_tokens, bob_tokens = tokens
                headers = {"Authorization": "Bearer " + alice_tokens["access_token"]}
                response = await client.get("/profile", headers=headers)
                assert response.status_code == 200 and response.json()["name"] == "Alice"
                response = await client.get("/data/users/", headers=headers)
                assert response.status_code == 200 and response.json()["total_data"] == 1
                assert response.json()["data"][0]["id"] == alice["id"]
                assert (
                    await client.get(f"/data/users/{bob['id']}", headers=headers)
                ).status_code == 404
                for record_id in ["abc", "0", "-1", "2147483648"]:
                    assert (
                        await client.get("/data/users/" + record_id, headers=headers)
                    ).status_code == 404
                for resource in ["users", "user_permissions", "user_tokens"]:
                    described = await client.get(f"/data/{resource}/describe", headers=headers)
                    assert described.status_code == 200
                    records = await client.get(f"/data/{resource}/", headers=headers)
                    assert records.status_code == 200 and records.json()["total_data"] == 1
                    assert "password" not in records.text and "refresh_hash" not in records.text
                    assert (
                        "access_token" not in records.text and "refresh_token" not in records.text
                    )
                    if resource != "users":
                        assert records.json()["data"][0]["user_id"] == alice["id"]

                # Elevate only the fixture user inside this isolated schema to test admin reads.
                async with factory() as session:
                    await session.execute(
                        update(UserPermissionSQLModel)
                        .where(UserPermissionSQLModel.user_id == alice["id"])
                        .values(permission="admin")
                    )
                    await session.commit()
                response = await client.get("/api/v1/data/users/?_pageSize=1", headers=headers)
                assert response.status_code == 200
                assert response.json()["total_data"] == 2 and response.json()["total_page"] == 2
                assert (
                    await client.get(f"/data/users/{bob['id']}", headers=headers)
                ).status_code == 200

                # Refresh compare-and-swap must allow exactly one concurrent winner.
                outcomes = await asyncio.gather(
                    *[
                        client.post(
                            "/refresh-token", json={"refresh_token": alice_tokens["refresh_token"]}
                        )
                        for _ in range(2)
                    ]
                )
                assert sorted(response.status_code for response in outcomes) == [200, 401]
                renewed = next(
                    response.json() for response in outcomes if response.status_code == 200
                )
                async with factory() as session:
                    stored = await session.scalar(
                        select(UserTokenSQLModel).where(UserTokenSQLModel.user_id == alice["id"])
                    )
                    assert stored.refresh_hash == token_hash(renewed["refresh_token"])
                    assert stored.refresh_hash != renewed["refresh_token"]
                assert (
                    await client.post("/logout", json={"refresh_token": renewed["refresh_token"]})
                ).status_code == 204
                for token in [alice_tokens["access_token"], renewed["access_token"]]:
                    assert (
                        await client.get("/profile", headers={"Authorization": "Bearer " + token})
                    ).status_code == 401
                assert (
                    await client.post(
                        "/refresh-token", json={"refresh_token": renewed["refresh_token"]}
                    )
                ).status_code == 401
                assert (
                    await client.get(
                        "/profile",
                        headers={"Authorization": "Bearer " + bob_tokens["access_token"]},
                    )
                ).status_code == 200

            async with engine.begin() as connection:
                await connection.run_sync(lambda conn: migrate(conn, command.downgrade, "base"))
                tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
                assert set(tables) <= {"alembic_version"}
                await connection.run_sync(lambda conn: migrate(conn, command.upgrade, "head"))
        finally:
            if engine is not None:
                await engine.dispose()
            if created:
                assert re.fullmatch(r"submission_test_[0-9a-f]{32}", schema)
                async with admin_engine.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin_engine.dispose()

    asyncio.run(run())

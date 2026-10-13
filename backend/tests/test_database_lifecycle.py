import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.database import connector, session


@pytest.mark.parametrize("exit_with_error", [False, True])
def test_lifespan_cleanup_and_mongo_dependency(monkeypatch, exit_with_error):
    monkeypatch.setattr(connector.config, "mongodb_enabled", True)
    engine = MagicMock()
    engine.dispose = AsyncMock()
    client = MagicMock()
    database = object()
    client.__getitem__.return_value = database
    monkeypatch.setattr(connector, "postgres_engine", engine)
    monkeypatch.setattr(connector, "AsyncIOMotorClient", MagicMock(return_value=client))
    monkeypatch.setattr(connector, "mongo_client", None)
    monkeypatch.setattr(connector, "mongo_db", None)
    monkeypatch.setattr(connector, "check_database_connections", AsyncMock())

    async def run():
        with pytest.raises(RuntimeError, match="not initialized"):
            session.get_mongodb()
        try:
            async with connector.lifespan(None):
                assert session.get_mongodb() is database
                if exit_with_error:
                    raise ValueError("simulated lifecycle failure")
        except ValueError:
            assert exit_with_error
        engine.dispose.assert_awaited_once()
        client.close.assert_called_once()
        assert connector.mongo_client is None
        with pytest.raises(RuntimeError, match="not initialized"):
            session.get_mongodb()

    asyncio.run(run())


def test_mongo_closes_if_postgres_dispose_fails(monkeypatch):
    monkeypatch.setattr(connector.config, "mongodb_enabled", True)
    engine = MagicMock()
    engine.dispose = AsyncMock(side_effect=RuntimeError("dispose failed"))
    client = MagicMock()
    monkeypatch.setattr(connector, "postgres_engine", engine)
    monkeypatch.setattr(connector, "AsyncIOMotorClient", MagicMock(return_value=client))
    monkeypatch.setattr(connector, "mongo_client", None)
    monkeypatch.setattr(connector, "mongo_db", None)
    monkeypatch.setattr(connector, "check_database_connections", AsyncMock())

    async def run():
        with pytest.raises(RuntimeError, match="dispose failed"):
            async with connector.lifespan(None):
                pass
        client.close.assert_called_once()
        assert connector.mongo_db is None

    asyncio.run(run())


@pytest.mark.parametrize("failing_db", [None, "postgres", "mongo"])
def test_connection_logs_reflect_real_probe_result(monkeypatch, caplog, failing_db):
    engine = MagicMock()
    connection = MagicMock()
    connection.execute = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine.connect.return_value = context
    client = MagicMock()
    client.admin.command = AsyncMock()
    if failing_db == "postgres":
        connection.execute.side_effect = ConnectionError("secret-must-not-be-logged")
    if failing_db == "mongo":
        client.admin.command.side_effect = ConnectionError("secret-must-not-be-logged")
    monkeypatch.setattr(connector, "postgres_engine", engine)
    monkeypatch.setattr(connector, "mongo_client", client)

    with caplog.at_level("INFO", logger="uvicorn.error"):
        asyncio.run(connector.check_database_connections())
    assert ("PostgreSQL connected successfully" in caplog.text) == (failing_db != "postgres")
    assert ("MongoDB connected successfully" in caplog.text) == (failing_db != "mongo")
    if failing_db is not None:
        assert "connection check failed" in caplog.text
    assert "secret-must-not-be-logged" not in caplog.text


@pytest.mark.parametrize("exit_with_error", [False, True])
def test_session_dependency_exits_context(monkeypatch, exit_with_error):
    db_session = object()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db_session)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(connector, "async_session_factory", MagicMock(return_value=context))

    async def run():
        dependency = session.get_postgres_db()
        assert await anext(dependency) is db_session
        if exit_with_error:
            with pytest.raises(ValueError, match="request failed"):
                await dependency.athrow(ValueError("request failed"))
        else:
            await dependency.aclose()
        context.__aexit__.assert_awaited_once()

    asyncio.run(run())

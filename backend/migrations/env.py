import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config.settings import Settings
from app.infrastructure.database.models.user_model import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# อ่านค่า DB จาก .env ชุดเดียวกับ API ไม่ใส่ password ลง alembic.ini
settings = Settings()
database_url = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.postgres_db_user,
    password=settings.postgres_db_password.get_secret_value(),
    host=settings.postgres_db_host,
    port=settings.postgres_db_port,
    database=settings.postgres_db_name,
)

# Base ตัวเดียวกับ UserSQLModel ที่ผู้ใช้เขียนอยู่
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if config.attributes.get("connection") is not None:
    do_run_migrations(config.attributes["connection"])
elif context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())

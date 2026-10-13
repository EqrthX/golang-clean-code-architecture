import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.settings import Settings

config = Settings()
logger = logging.getLogger("uvicorn.error")

# แยกข้อมูลแต่ละส่วน ไม่ต้อง escape อักขระพิเศษใน password เอง
url_object = URL.create(
    drivername="postgresql+asyncpg",
    username=config.postgres_db_user,
    password=config.postgres_db_password.get_secret_value(),
    host=config.postgres_db_host,
    port=config.postgres_db_port,
    database=config.postgres_db_name,
)

postgres_engine = create_async_engine(url_object, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(
    bind=postgres_engine,
    autoflush=False,
    expire_on_commit=False,
)

mongo_client: AsyncIOMotorClient | None = None
mongo_db: AsyncIOMotorDatabase | None = None


async def check_database_connections() -> None:
    async def check_postgres() -> None:
        async with postgres_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(check_postgres(), timeout=5)
    except Exception as exc:
        # ไม่แสดง exception text เพราะอาจมี URL หรือ credentials
        logger.warning("[DB] PostgreSQL connection check failed (%s)", type(exc).__name__)
    else:
        logger.info("[DB] PostgreSQL connected successfully")

    if mongo_client is not None:
        try:
            await asyncio.wait_for(mongo_client.admin.command("ping"), timeout=2)
        except Exception as exc:
            logger.warning(
                "[DB] MongoDB connection check failed (%s); check whether MongoDB is running",
                type(exc).__name__,
            )
        else:
            logger.info("[DB] MongoDB connected successfully")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global mongo_client, mongo_db

    try:
        if config.mongodb_enabled:
            mongo_client = AsyncIOMotorClient(config.mongodb_db_atlas_uri)
            mongo_db = mongo_client[config.mongodb_db_name]
        # ตรวจจริงก่อนแสดงข้อความสำเร็จ แต่คงให้แอปเปิดได้ถ้า DB ยังไม่พร้อม
        await check_database_connections()
        yield
    finally:
        # ปิด MongoDB แม้การ dispose ของ PostgreSQL ล้มเหลว
        try:
            await postgres_engine.dispose()
        finally:
            if mongo_client is not None:
                mongo_client.close()
            mongo_client = None
            mongo_db = None

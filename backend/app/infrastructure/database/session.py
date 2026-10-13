from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import connector


async def get_postgres_db() -> AsyncIterator[AsyncSession]:
    # หนึ่ง session ต่อการเรียก dependency; context manager ปิด session ให้
    # การ commit เป็นหน้าที่ของ usecase/repository ที่เลือกขอบเขต transaction
    async with connector.async_session_factory() as session:
        yield session


def get_mongodb() -> AsyncIOMotorDatabase:
    # อ่านจาก module ตอนเรียก เพื่อได้ค่าที่ lifespan initialize ไว้ล่าสุด
    if connector.mongo_db is None:
        raise RuntimeError("MongoDB is not initialized inside lifespan.")
    return connector.mongo_db

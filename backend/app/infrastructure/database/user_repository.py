from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.auth import UserSession
from app.domain.entities.user import User
from app.domain.errors import DuplicateEmailError
from app.infrastructure.database.models.user_model import (
    UserPermissionSQLModel,
    UserSQLModel,
    UserTokenSQLModel,
)
from app.infrastructure.mapper.user_mapper import UserMapper


async def check_user_exists(session: AsyncSession, email: str) -> int | None:
    stmt = select(UserSQLModel.id).where(UserSQLModel.email == email).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _is_email_conflict(error: IntegrityError) -> bool:
    # ตรวจ constraint เฉพาะ email เพื่อไม่กลืน integrity errors ประเภทอื่น
    original = error.orig
    cause = getattr(original, "__cause__", None)
    return (
        getattr(original, "sqlstate", None) == "23505"
        and getattr(cause, "constraint_name", None) == "uq_users_email"
    )


async def create_user(session: AsyncSession, *, name: str, email: str, password_hash: str) -> User:
    user_model = UserSQLModel(name=name, email=email, password=password_hash)
    session.add(user_model)
    try:
        await session.flush()
        await session.refresh(user_model)
        session.add(UserPermissionSQLModel(user_id=user_model.id, permission="user"))
        user = UserMapper.to_entity(user_model)
        await session.commit()
        return user
    except IntegrityError as exc:
        await session.rollback()
        if _is_email_conflict(exc):
            raise DuplicateEmailError() from exc
        raise
    except Exception:
        await session.rollback()
        raise


async def get_credentials_by_email(session: AsyncSession, email: str) -> tuple[int, str] | None:
    stmt = (
        select(UserSQLModel.id, UserSQLModel.password).where(UserSQLModel.email == email).limit(1)
    )
    result = await session.execute(statement=stmt)
    row = result.one_or_none()
    return None if row is None else (row[0], row[1])


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(UserSQLModel).where(UserSQLModel.id == user_id)
    result = await session.execute(statement=stmt)
    user_model = result.scalar_one_or_none()

    if user_model is None:
        return None

    return UserMapper.to_entity(user_model)


class PostgresUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_user_exists(self, email: str) -> int | None:
        return await check_user_exists(self.session, email)

    async def create_user(self, name: str, email: str, password_hash: str) -> User:
        return await create_user(self.session, name=name, email=email, password_hash=password_hash)

    async def get_credentials_by_email(self, email: str) -> tuple[int, str] | None:
        return await get_credentials_by_email(self.session, email=email)

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await get_user_by_id(self.session, user_id=user_id)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def create_session(
        self, session_id: str, user_id: int, refresh_hash: str, expires_at: datetime
    ) -> None:
        self.session.add(
            UserTokenSQLModel(
                id=session_id, user_id=user_id, refresh_hash=refresh_hash, expires_at=expires_at
            )
        )
        await self._commit()

    async def get_session(self, session_id: str, user_id: int) -> UserSession | None:
        row = await self.session.scalar(
            select(UserTokenSQLModel).where(
                UserTokenSQLModel.id == session_id, UserTokenSQLModel.user_id == user_id
            )
        )
        return (
            None
            if row is None
            else UserSession(row.id, row.user_id, row.refresh_hash, row.expires_at)
        )

    async def rotate_session(
        self, session_id: str, user_id: int, old_hash: str, new_hash: str
    ) -> bool:
        result = await self.session.execute(
            update(UserTokenSQLModel)
            .where(
                UserTokenSQLModel.id == session_id,
                UserTokenSQLModel.user_id == user_id,
                UserTokenSQLModel.refresh_hash == old_hash,
                UserTokenSQLModel.expires_at > func.now(),
            )
            .values(refresh_hash=new_hash, updated_at=func.now())
            .returning(UserTokenSQLModel.id)
        )
        changed = result.scalar_one_or_none() is not None
        await self._commit()
        return changed

    async def delete_session(self, session_id: str, user_id: int, refresh_hash: str) -> bool:
        result = await self.session.execute(
            delete(UserTokenSQLModel)
            .where(
                UserTokenSQLModel.id == session_id,
                UserTokenSQLModel.user_id == user_id,
                UserTokenSQLModel.refresh_hash == refresh_hash,
            )
            .returning(UserTokenSQLModel.id)
        )
        removed = result.scalar_one_or_none() is not None
        await self._commit()
        return removed

    async def get_permission(self, user_id: int) -> str:
        permission = await self.session.scalar(
            select(UserPermissionSQLModel.permission).where(
                UserPermissionSQLModel.user_id == user_id
            )
        )
        return permission or "user"

    @staticmethod
    def _public_record(row) -> dict:
        if isinstance(row, UserSQLModel):
            return asdict(UserMapper.to_entity(row))
        if isinstance(row, UserPermissionSQLModel):
            return {
                "id": row.id,
                "user_id": row.user_id,
                "permission": row.permission,
                "updated_at": row.updated_at,
            }
        return {
            "id": row.id,
            "user_id": row.user_id,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _model(resource: str):
        return {
            "users": UserSQLModel,
            "user_tokens": UserTokenSQLModel,
            "user_permissions": UserPermissionSQLModel,
        }[resource]

    async def list_records(
        self, resource: str, user_id: int, admin: bool, page: int, page_size: int
    ) -> tuple[list[dict], int]:
        model = self._model(resource)
        scope = [] if admin else [(model.id if resource == "users" else model.user_id) == user_id]
        total = await self.session.scalar(select(func.count()).select_from(model).where(*scope))
        rows = await self.session.scalars(
            select(model)
            .where(*scope)
            .order_by(model.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [self._public_record(row) for row in rows], total or 0

    async def get_record(
        self, resource: str, record_id: str, user_id: int, admin: bool
    ) -> dict | None:
        model = self._model(resource)
        try:
            if resource == "user_tokens":
                identifier = str(UUID(record_id))
            else:
                if not record_id.isascii() or not record_id.isdecimal():
                    return None
                identifier = int(record_id)
                if not 0 < identifier <= 2147483647:
                    return None
        except ValueError:
            return None
        scope = [] if admin else [(model.id if resource == "users" else model.user_id) == user_id]
        row = await self.session.scalar(select(model).where(model.id == identifier, *scope))
        return None if row is None else self._public_record(row)

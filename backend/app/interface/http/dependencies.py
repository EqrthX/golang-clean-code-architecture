from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.errors import InvalidTokenError
from app.domain.user_repository import UserRepository
from app.infrastructure.database.session import get_postgres_db
from app.infrastructure.database.user_repository import PostgresUserRepository
from app.usecases.usecease_auth import authenticate_user

security = HTTPBearer()


def get_user_repository(db: Annotated[AsyncSession, Depends(get_postgres_db)]) -> UserRepository:
    return PostgresUserRepository(db)


def unauthorized(detail: str = "Token ไม่ถูกต้องหรือหมดอายุ") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    try:
        return await authenticate_user(repository, credentials.credentials)
    except InvalidTokenError:
        raise unauthorized() from None

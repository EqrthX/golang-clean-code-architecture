import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.config.settings import Settings
from app.domain.entities.auth import TokenPair
from app.domain.entities.user import User
from app.domain.errors import DuplicateEmailError, InvalidTokenError, PasswordVerifyError
from app.domain.user_repository import UserRepository

config = Settings()


def hashPassword(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password) < 8 or len(password_bytes) > 72:
        raise ValueError("Password must have at least 8 characters and at most 72 UTF-8 bytes")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    lifetime = (
        expires_delta if expires_delta is not None else timedelta(minutes=config.jwt_access_expires)
    )
    if lifetime <= timedelta(0):
        raise ValueError("Token lifetime must be positive")
    claims = {**data, "exp": datetime.now(timezone.utc) + lifetime}
    return jwt.encode(claims, config.secret_key.get_secret_value(), algorithm="HS256")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _token_pair(user_id: int, session_id: str, expires_at: datetime) -> TokenPair:
    access_lifetime = min(
        timedelta(minutes=config.jwt_access_expires), expires_at - datetime.now(timezone.utc)
    )
    access = create_access_token(
        {"sub": str(user_id), "sid": session_id, "type": "access"}, access_lifetime
    )
    refresh = jwt.encode(
        {
            "sub": str(user_id),
            "sid": session_id,
            "type": "refresh",
            "jti": str(uuid4()),
            "exp": expires_at,
        },
        config.secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return TokenPair(access_token=access, refresh_token=refresh)


def verify_token(token: str, token_type: str = "access") -> dict:
    """Validate claims without depending on FastAPI or HTTP credentials."""
    try:
        claims = jwt.decode(
            token,
            config.secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "type"]},
        )
        subject = claims["sub"]
        if not subject.isascii() or not subject.isdecimal() or not 0 < int(subject) <= 2147483647:
            raise InvalidTokenError()
        if claims["type"] != token_type or str(UUID(claims["sid"])) != claims["sid"]:
            raise InvalidTokenError()
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise InvalidTokenError() from None


async def register_user(
    repository: UserRepository, *, name: str, email: str, password: str
) -> User:
    if await repository.check_user_exists(email) is not None:
        raise DuplicateEmailError()
    password_hash = await asyncio.to_thread(hashPassword, password)
    return await repository.create_user(name=name, email=email, password_hash=password_hash)


async def login_user(repository: UserRepository, email: str, password: str) -> TokenPair:
    credentials = await repository.get_credentials_by_email(email=email)
    if credentials is None:
        raise PasswordVerifyError()
    user_id, password_hash = credentials
    try:
        matched = await asyncio.to_thread(bcrypt.checkpw, password.encode(), password_hash.encode())
    except ValueError:
        raise PasswordVerifyError() from None
    if not matched:
        raise PasswordVerifyError()
    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=config.jwt_refresh_expires)
    tokens = _token_pair(user_id, session_id, expires_at)
    await repository.create_session(
        session_id, user_id, token_hash(tokens.refresh_token), expires_at
    )
    return tokens


async def get_profile(repository: UserRepository, user_id: int) -> User | None:
    return await repository.get_user_by_id(user_id)


async def authenticate_user(repository: UserRepository, token: str) -> User:
    claims = verify_token(token)
    user_id = int(claims["sub"])
    session = await repository.get_session(claims["sid"], user_id)
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        raise InvalidTokenError()
    user = await get_profile(repository, user_id)
    if user is None:
        raise InvalidTokenError()
    return user


async def refresh_user_token(repository: UserRepository, token: str) -> TokenPair:
    claims = verify_token(token, "refresh")
    user_id, session_id = int(claims["sub"]), claims["sid"]
    session = await repository.get_session(session_id, user_id)
    old_hash = token_hash(token)
    if (
        session is None
        or session.expires_at <= datetime.now(timezone.utc)
        or not hmac.compare_digest(session.refresh_hash, old_hash)
    ):
        raise InvalidTokenError()
    if await get_profile(repository, user_id) is None:
        raise InvalidTokenError()
    tokens = _token_pair(user_id, session_id, session.expires_at)
    # Compare-and-swap makes concurrent reuse of one refresh token fail.
    if not await repository.rotate_session(
        session_id, user_id, old_hash, token_hash(tokens.refresh_token)
    ):
        raise InvalidTokenError()
    return tokens


async def logout_user(repository: UserRepository, token: str) -> None:
    claims = verify_token(token, "refresh")
    if not await repository.delete_session(claims["sid"], int(claims["sub"]), token_hash(token)):
        raise InvalidTokenError()

from datetime import datetime
from typing import Protocol

from app.domain.entities.auth import UserSession
from app.domain.entities.user import User


class UserRepository(Protocol):
    async def check_user_exists(self, email: str) -> int | None: ...

    async def create_user(self, name: str, email: str, password_hash: str) -> User: ...

    async def get_credentials_by_email(self, email: str) -> tuple[int, str] | None: ...

    async def get_user_by_id(self, user_id: int) -> User | None: ...

    async def create_session(
        self, session_id: str, user_id: int, refresh_hash: str, expires_at: datetime
    ) -> None: ...

    async def get_session(self, session_id: str, user_id: int) -> UserSession | None: ...

    async def rotate_session(
        self, session_id: str, user_id: int, old_hash: str, new_hash: str
    ) -> bool: ...

    async def delete_session(self, session_id: str, user_id: int, refresh_hash: str) -> bool: ...

    async def get_permission(self, user_id: int) -> str: ...

    async def list_records(
        self, resource: str, user_id: int, admin: bool, page: int, page_size: int
    ) -> tuple[list[dict], int]: ...

    async def get_record(
        self, resource: str, record_id: str, user_id: int, admin: bool
    ) -> dict | None: ...

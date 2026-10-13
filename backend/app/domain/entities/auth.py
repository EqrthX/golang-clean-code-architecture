from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class UserSession:
    id: str
    user_id: int
    refresh_hash: str
    expires_at: datetime

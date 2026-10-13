"""User data independent of HTTP schemas and database models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class User:
    id: int
    name: str
    email: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def deactivate(self):
        self.updated_at = datetime.now(timezone.utc)  # อัปเดตเวลาเมื่อมีการเปลี่ยนแปลงสถานะ

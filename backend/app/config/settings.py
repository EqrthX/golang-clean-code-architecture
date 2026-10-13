from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="FASTAPIAPP_",
        extra="forbid",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    name: str = "Clean Architecture API"
    version: str = "0.1.0"
    postgres_db_name: str = "clean_architecture"
    postgres_db_user: str = "app"
    postgres_db_password: SecretStr
    postgres_db_host: str = "127.0.0.1"
    postgres_db_port: int = Field(default=5432, ge=1, le=65535)
    mongodb_db_atlas_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_enabled: bool = False
    mongodb_db_name: str = "clean_architecture"
    secret_key: SecretStr = Field(min_length=32)
    jwt_access_expires: int = Field(default=30, gt=0)
    jwt_refresh_expires: int = Field(default=7, gt=0)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

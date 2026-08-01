"""System configuration engine powered by Pydantic Settings v2."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL Connection Settings."""

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    user: str = Field(default="router_user", alias="POSTGRES_USER")
    password: str = Field(default="router_password", alias="POSTGRES_PASSWORD")
    db: str = Field(default="notification_router", alias="POSTGRES_DB")
    pool_size: int = Field(default=20, alias="POSTGRES_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="POSTGRES_MAX_OVERFLOW")

    @property
    def async_url(self) -> str:
        """Construct SQLAlchemy Async PostgreSQL Connection DSN."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Redis Cache Connection Settings."""

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    default_ttl: int = Field(default=3600, alias="CACHE_TTL_DEFAULT_SECONDS")
    preference_ttl: int = Field(default=86400, alias="PREFERENCE_CACHE_TTL_SECONDS")


class Settings(BaseSettings):
    """Global Application Configuration Settings Root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    app_name: str = Field(default="whatsapp-notification-router", alias="APP_NAME")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_STR")

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton instance of system configuration settings."""
    return Settings()

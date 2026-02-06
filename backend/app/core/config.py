"""Application configuration from environment variables."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "PaceTrail"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Security
    secret_key: str = "change-me-in-production-use-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    # Cookie for refresh token (local dev: Secure=false)
    cookie_secure: bool = False
    cookie_same_site: str = "lax"
    cookie_name: str = "refresh_token"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://pacetrail:pacetrail@localhost:5432/pacetrail"

    # Redis (optional)
    redis_url: str | None = None

    # Rate limit (stub: requests per minute per IP)
    rate_limit_per_minute: int = 60

    # Upload (local dev storage for raw GPX/TCX)
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50
    allowed_upload_extensions: List[str] = ["gpx", "tcx"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

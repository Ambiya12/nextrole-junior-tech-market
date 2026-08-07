"""Validated application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEXTROLE_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str | None = Field(default=None, repr=False)
    france_travail_client_id: SecretStr | None = Field(default=None, repr=False)
    france_travail_client_secret: SecretStr | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object per process."""

    return Settings()

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

NonEmptyStr = Annotated[str, Field(min_length=1)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_ENV: NonEmptyStr
    APP_NAME: NonEmptyStr
    APP_HOST: NonEmptyStr
    APP_PORT: int
    CORS_ORIGINS: list[str]

    # Database (PostgreSQL)
    DATABASE_URL: Annotated[SecretStr, Field(min_length=1)]

    # Redis
    REDIS_URL: NonEmptyStr

    # Security & JWT
    JWT_SECRET_KEY: Annotated[SecretStr, Field(min_length=32)]
    JWT_ALGORITHM: NonEmptyStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # LLM API
    OPENAI_API_KEY: SecretStr
    ANTHROPIC_API_KEY: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

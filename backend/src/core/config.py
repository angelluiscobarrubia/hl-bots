"""Configuración central cargada desde variables de entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Lee las variables de entorno una sola vez."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://admin:securepass@localhost:5432/bot_platform",
        description="URL async de SQLAlchemy",
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Encryption
    master_encryption_key: str = Field(
        default="",
        description=(
            "Clave Fernet (32 bytes url-safe base64). Genera con: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ),
    )

    # JWT
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440

    # Hyperliquid
    hyperliquid_mainnet_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_testnet_url: str = "https://api.hyperliquid-testnet.xyz"

    # Telegram
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Singleton para importación rápida
settings = get_settings()

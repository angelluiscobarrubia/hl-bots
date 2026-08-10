"""Tokens JWT (access + refresh) con PyJWT."""

from datetime import datetime, timedelta, timezone

import jwt

from src.core.config import settings


def create_access_token(user_id: int, auth_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "auth_version": auth_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int, auth_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "auth_version": auth_version,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decodifica y valida firma+expiración. Lanza jwt.PyJWTError si inválido."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

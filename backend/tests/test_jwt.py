"""Tests para el adaptador de tokens JWT."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from src.adapters.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.core.config import settings


def test_access_token_claims():
    """create_access_token emite un token con los claims esperados."""
    token = create_access_token(42, 3)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert payload["auth_version"] == 3


def test_refresh_token_type_and_expiry():
    """create_refresh_token emite un token con type=refresh y exp mayor que access."""
    access_token = create_access_token(42, 3)
    refresh_token = create_refresh_token(42, 3)

    access_payload = decode_token(access_token)
    refresh_payload = decode_token(refresh_token)

    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]


def test_expired_token_raises():
    """Un token con exp en el pasado lanza ExpiredSignatureError."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "42",
        "type": "access",
        "auth_version": 1,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_wrong_secret_raises():
    """Un token firmado con otra clave lanza InvalidSignatureError."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "42",
        "type": "access",
        "auth_version": 1,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(payload, "different-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token)

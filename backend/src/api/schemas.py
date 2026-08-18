"""Pydantic schemas for API request/response validation."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    must_change_password: bool



class CreateApiKeyRequest(BaseModel):
    """Request para crear una API key cifrada."""

    user_id: int
    bot_id: str
    exchange: str = "hyperliquid"
    api_key: str
    secret: str

    @field_validator("bot_id")
    @classmethod
    def bot_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("bot_id no puede estar vacío")
        return v

    @field_validator("api_key", "secret")
    @classmethod
    def secrets_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Los secretos no pueden estar vacíos")
        return v


class ApiKeyOut(BaseModel):
    """Response con metadatos de API key (nunca plaintext)."""

    id: int
    user_id: int
    bot_id: str
    exchange: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyListResponse(BaseModel):
    """Response para listado de API keys."""

    keys: list[ApiKeyOut]
    total: int

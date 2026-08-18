"""Rutas de administración de API keys (solo admin).

Las API keys se reciben en plaintext por HTTPS, se cifran inmediatamente
con Fernet, y nunca se devuelven en respuestas HTTP.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import require_permission
from src.api.schemas import ApiKeyListResponse, ApiKeyOut, CreateApiKeyRequest
from src.core.models import User
from src.core.security.permissions import Perm
from src.core.services.api_key_service import (
    ApiKeyAlreadyExistsError,
    ApiKeyNotFoundError,
    get_api_key_service,
)

router = APIRouter(prefix="/admin/api-keys", tags=["admin", "api-keys"])


@router.post("", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest,
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> ApiKeyOut:
    """Crea una API key cifrada para un bot."""
    try:
        db_key = await get_api_key_service().create_key(
            user_id=body.user_id,
            bot_id=body.bot_id,
            exchange=body.exchange,
            api_key=body.api_key,
            secret=body.secret,
        )
    except ApiKeyAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una API key para bot_id={body.bot_id}",
        ) from None
    return ApiKeyOut.model_validate(db_key)


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    user_id: int | None = None,
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> ApiKeyListResponse:
    """Lista API keys (solo metadatos, nunca plaintext)."""
    keys = await get_api_key_service().list_keys(user_id=user_id)
    return ApiKeyListResponse(
        keys=[ApiKeyOut.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.get("/{bot_id}", response_model=ApiKeyOut)
async def get_api_key(
    bot_id: str,
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> ApiKeyOut:
    """Obtiene metadatos de una API key por bot_id."""
    try:
        db_key = await get_api_key_service().get_key(bot_id)
    except ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe API key para bot_id={bot_id}",
        ) from None
    return ApiKeyOut.model_validate(db_key)


@router.post("/{bot_id}/deactivate", response_model=ApiKeyOut)
async def deactivate_api_key(
    bot_id: str,
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> ApiKeyOut:
    """Desactiva una API key (is_active=False) sin borrarla."""
    try:
        db_key = await get_api_key_service().deactivate_key(bot_id)
    except ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe API key para bot_id={bot_id}",
        ) from None
    return ApiKeyOut.model_validate(db_key)

"""Rutas de gestión de bots (crear, listar, arrancar, detener).

Cada usuario solo puede operar sobre sus propios bots; el acceso a bots de
otros usuarios devuelve 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_user
from src.api.schemas import (
    BotListResponse,
    BotOut,
    CreateBotRequest,
    StartBotRequest,
)
from src.core.models import Bot as BotModel
from src.core.models import User
from src.core.services.bot_manager import BotNotFoundError, get_bot_manager

router = APIRouter(prefix="/bots", tags=["bots"])


async def _get_owned_bot(bot_id: int, user: User) -> BotModel:
    """Devuelve el bot si existe y pertenece al usuario; si no, lanza HTTPException."""
    try:
        db_bot = await get_bot_manager().get_bot(bot_id)
    except BotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe bot con id={bot_id}",
        ) from None
    if db_bot.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este bot",
        )
    return db_bot


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def create_bot(
    body: CreateBotRequest,
    user: User = Depends(get_current_user),
) -> BotOut:
    """Crea un bot para el usuario autenticado."""
    entity = await get_bot_manager().create_bot(
        user_id=user.id,
        name=body.name,
        strategy=body.strategy,
        config=body.config,
        is_paper=body.is_paper,
    )
    db_bot = await get_bot_manager().get_bot(int(entity.id))
    return BotOut.model_validate(db_bot)


@router.get("", response_model=BotListResponse)
async def list_bots(user: User = Depends(get_current_user)) -> BotListResponse:
    """Lista los bots del usuario autenticado."""
    db_bots = await get_bot_manager().list_bot_models(user.id)
    return BotListResponse(
        bots=[BotOut.model_validate(b) for b in db_bots],
        total=len(db_bots),
    )


@router.get("/{bot_id}", response_model=BotOut)
async def get_bot(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> BotOut:
    """Devuelve los detalles de un bot (solo el dueño)."""
    db_bot = await _get_owned_bot(bot_id, user)
    return BotOut.model_validate(db_bot)


@router.post("/{bot_id}/start", response_model=BotOut)
async def start_bot(
    bot_id: int,
    body: StartBotRequest,
    user: User = Depends(get_current_user),
) -> BotOut:
    """Arranca un bot (solo el dueño)."""
    await _get_owned_bot(bot_id, user)
    try:
        await get_bot_manager().start_bot(bot_id, body.api_key, body.api_secret)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un bot real requiere API key y secret",
        ) from None
    db_bot = await get_bot_manager().get_bot(bot_id)
    return BotOut.model_validate(db_bot)


@router.post("/{bot_id}/stop", response_model=BotOut)
async def stop_bot(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> BotOut:
    """Detiene un bot (solo el dueño)."""
    await _get_owned_bot(bot_id, user)
    await get_bot_manager().stop_bot(bot_id)
    db_bot = await get_bot_manager().get_bot(bot_id)
    return BotOut.model_validate(db_bot)

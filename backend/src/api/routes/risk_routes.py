"""Rutas de gestión de riesgo de bots.

Permiten consultar el estado de riesgo de un bot y detener/reanudar su trading
manualmente. Cada usuario solo puede operar sobre sus propios bots; el acceso a
bots de otros usuarios devuelve 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_user
from src.api.schemas import RiskStatusResponse
from src.core.models import User
from src.core.services.bot_manager import BotNotFoundError, get_bot_manager
from src.core.services.risk_manager import RiskManager

router = APIRouter(prefix="/bots/{bot_id}/risk", tags=["risk"])


async def _get_owned_risk_manager(bot_id: int, user: User) -> RiskManager:
    """Devuelve el RiskManager del bot si existe y pertenece al usuario.

    Raises:
        HTTPException: 404 si el bot no existe o no tiene risk manager activo,
            403 si el bot pertenece a otro usuario.
    """
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
    risk_manager = get_bot_manager().get_risk_manager(bot_id)
    if risk_manager is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El bot no está corriendo o no tiene risk manager activo",
        )
    return risk_manager


@router.get("/status", response_model=RiskStatusResponse)
async def get_risk_status(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> RiskStatusResponse:
    """Devuelve el estado de riesgo actual del bot (solo el dueño)."""
    risk_manager = await _get_owned_risk_manager(bot_id, user)
    data = await risk_manager.status()
    return RiskStatusResponse(**data)


@router.post("/halt", response_model=RiskStatusResponse)
async def halt_bot(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> RiskStatusResponse:
    """Detiene manualmente el trading del bot (solo el dueño)."""
    risk_manager = await _get_owned_risk_manager(bot_id, user)
    risk_manager.halt("Manually halted by user")
    data = await risk_manager.status()
    return RiskStatusResponse(**data)


@router.post("/resume", response_model=RiskStatusResponse)
async def resume_bot(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> RiskStatusResponse:
    """Reanuda el trading del bot tras un halt (solo el dueño)."""
    risk_manager = await _get_owned_risk_manager(bot_id, user)
    risk_manager.resume()
    data = await risk_manager.status()
    return RiskStatusResponse(**data)

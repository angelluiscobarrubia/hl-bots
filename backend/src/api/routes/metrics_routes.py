"""Rutas de métricas de bots (métricas agregadas, trades y curva de equity).

Cada usuario solo puede consultar las métricas de sus propios bots; el acceso
a bots de otros usuarios devuelve 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_current_user
from src.api.schemas import (
    EquityCurveResponse,
    EquityPoint,
    MetricsResponse,
    TradeOut,
)
from src.core.models import User
from src.core.services.bot_manager import BotNotFoundError, get_bot_manager
from src.core.services.metrics_service import get_metrics_service

router = APIRouter(prefix="/bots/{bot_id}", tags=["metrics"])


async def _get_owned_bot(bot_id: int, user: User) -> None:
    """Comprueba que el bot existe y pertenece al usuario.

    Raises:
        HTTPException: 404 si el bot no existe, 403 si pertenece a otro usuario.
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


@router.get("/metrics", response_model=MetricsResponse)
async def get_bot_metrics(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> MetricsResponse:
    """Devuelve las métricas agregadas de un bot (solo el dueño)."""
    await _get_owned_bot(bot_id, user)
    data = await get_metrics_service().get_bot_metrics(bot_id, user.id)
    return MetricsResponse(**data)


@router.get("/trades", response_model=list[TradeOut])
async def get_bot_trades(
    bot_id: int,
    user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TradeOut]:
    """Devuelve los trades de un bot paginados (solo el dueño)."""
    await _get_owned_bot(bot_id, user)
    trades = await get_metrics_service().get_bot_trades(
        bot_id, user.id, limit=limit, offset=offset
    )
    return [TradeOut(**t) for t in trades]


@router.get("/equity-curve", response_model=EquityCurveResponse)
async def get_bot_equity_curve(
    bot_id: int,
    user: User = Depends(get_current_user),
) -> EquityCurveResponse:
    """Devuelve la curva de equity (P&L acumulado) de un bot (solo el dueño)."""
    await _get_owned_bot(bot_id, user)
    points = await get_metrics_service().get_equity_curve(bot_id, user.id)
    return EquityCurveResponse(
        bot_id=bot_id,
        points=[EquityPoint(**p) for p in points],
    )

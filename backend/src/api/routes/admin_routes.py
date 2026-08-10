"""Rutas de administración de usuarios (solo admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.database.session import get_db
from src.api.dependencies import require_permission
from src.api.schemas import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserOut,
)
from src.core.models import User
from src.core.security.permissions import Perm
from src.core.services.auth_service import auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserOut:
    try:
        user = await auth_service.create_user(body.email, body.password, role=body.role)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El email ya existe"
        ) from None
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        user.role = body.role
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
async def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    await auth_service.reset_password(user, body.new_password)
    await db.refresh(user)
    return UserOut.model_validate(user)

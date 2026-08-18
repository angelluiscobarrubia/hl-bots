"""Base SQLAlchemy + modelos ORM.

Los modelos concretos (Bot, User, Order, etc.) se irán añadiendo aquí.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""

    pass


class TimestampMixin:
    """Mixin con created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base, TimestampMixin):
    """Usuario de la plataforma."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    auth_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

class ApiKey(Base, TimestampMixin):
    """API key cifrada de un exchange (Hyperliquid) asociada a un bot y un usuario.

    Nunca almacena plaintext. Solo ciphertext Fernet.
    El descifrado ocurre exclusivamente en RAM al instanciar el adapter.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False,
        comment="FK lógica a users.id (sin FK para evitar acoplamiento)"
    )
    bot_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False,
        comment="Identificador del bot al que pertenece esta clave"
    )
    exchange: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Nombre del exchange (ej: 'hyperliquid')"
    )
    encrypted_api_key: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="API key cifrada con Fernet (base64-urlsafe)"
    )
    encrypted_api_secret: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="API secret cifrado con Fernet (base64-urlsafe)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Si False, la clave está revocada y no debe usarse"
    )


class Bot(Base, TimestampMixin):
    """Bot de trading configurado por un usuario."""

    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False,
        comment="FK lógica a users.id (sin FK para evitar acoplamiento)"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nombre del plugin de estrategia a usar"
    )
    symbol: Mapped[str] = mapped_column(
        String(50), default="BTC-USD", nullable=False
    )
    is_paper: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="True = paper trading, False = trading real"
    )
    config_json: Mapped[str] = mapped_column(
        Text, default="{}", nullable=False,
        comment="Configuración del bot en JSON (dict serializado)"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="stopped", nullable=False,
        comment="Estado: stopped | running | paused | error"
    )
    trades: Mapped[list[Trade]] = relationship(
        back_populates="bot", cascade="all, delete-orphan"
    )


class Trade(Base):
    """Trade ejecutado por un bot (persistido para métricas)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("bots.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" | "sell"
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    bot: Mapped[Bot] = relationship(back_populates="trades")

"""Base SQLAlchemy + modelos ORM.

Los modelos concretos (Bot, User, Order, etc.) se irán añadiendo aquí.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

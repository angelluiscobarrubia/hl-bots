"""Tests para el modelo ApiKey."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.core.models import ApiKey


class TestApiKeyModel:
    """Tests del modelo ApiKey."""

    async def test_create_api_key_defaults(self, db_session):
        """Crear un ApiKey con valores por defecto funciona."""
        api_key = ApiKey(
            user_id=1,
            bot_id="bot-001",
            exchange="hyperliquid",
            encrypted_api_key="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            encrypted_api_secret="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)

        assert api_key.id is not None
        assert api_key.user_id == 1
        assert api_key.bot_id == "bot-001"
        assert api_key.exchange == "hyperliquid"
        assert api_key.is_active is True  # default
        assert api_key.created_at is not None
        assert api_key.updated_at is not None

    async def test_bot_id_unique(self, db_session):
        """Dos ApiKey con el mismo bot_id violan la constraint unique."""
        api_key1 = ApiKey(
            user_id=1,
            bot_id="bot-dup",
            exchange="hyperliquid",
            encrypted_api_key="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            encrypted_api_secret="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
        )
        db_session.add(api_key1)
        await db_session.commit()

        api_key2 = ApiKey(
            user_id=2,
            bot_id="bot-dup",  # mismo bot_id
            exchange="hyperliquid",
            encrypted_api_key="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            encrypted_api_secret="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
        )
        db_session.add(api_key2)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_required_fields_not_nullable(self, db_session):
        """Campos requeridos no aceptan NULL."""
        api_key = ApiKey(
            user_id=None,  # type: ignore[arg-type]
            bot_id="bot-x",
            exchange="hyperliquid",
            encrypted_api_key="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            encrypted_api_secret="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
        )
        db_session.add(api_key)
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_is_active_can_be_deactivated(self, db_session):
        """Se puede desactivar una clave (is_active=False)."""
        api_key = ApiKey(
            user_id=1,
            bot_id="bot-deact",
            exchange="hyperliquid",
            encrypted_api_key="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            encrypted_api_secret="gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw==",
            is_active=False,
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        assert api_key.is_active is False

    async def test_multiple_keys_per_user_different_bots(self, db_session):
        """Un usuario puede tener múltiples claves (una por bot)."""
        for i in range(3):
            api_key = ApiKey(
                user_id=1,
                bot_id=f"bot-{i}",
                exchange="hyperliquid",
                encrypted_api_key=f"gAAAAABqg-XZCy1wzsodkWVWVf-iHTaif1ajUXw0gVGP-QF4aq4_LnKWZWpRIB9OvtVxBqc2x2vp9_lL4gI4Pd-4qlWeNwbhyw{i:02d}==",
                encrypted_api_secret=f"gAAAAABqg-XZ4-MWHQ8eEI8vF_KfsS_lwdKQ02hCHvE9-gysPuxVJZL1DLjQsTy_sHWuGqkZnkgKq4x3QiHFxpVRAFI94T0E{i:02d}==",
            )
            db_session.add(api_key)
        await db_session.commit()

        result = await db_session.execute(
            select(ApiKey).where(ApiKey.user_id == 1)
        )
        keys = result.scalars().all()
        assert len(keys) == 3

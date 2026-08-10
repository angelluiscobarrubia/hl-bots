"""CLI: crear usuario admin inicial."""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from src.adapters.database.session import async_session_factory
from src.core.models import User
from src.core.services.auth_service import auth_service


async def _main(email: str, password: str) -> None:
    user = await auth_service.create_user(email, password, role="admin")
    # Admin doesn't need to change password on first login
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        db_user = result.scalar_one()
        db_user.must_change_password = False
        await session.commit()
    print(f"Admin creado: {user.email} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear usuario admin inicial")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True, help="Mínimo 8 caracteres")
    args = parser.parse_args()
    if len(args.password) < 8:
        raise SystemExit("La contraseña debe tener al menos 8 caracteres")
    asyncio.run(_main(args.email, args.password))


if __name__ == "__main__":
    main()

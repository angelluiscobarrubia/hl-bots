"""Port del resolver de permisos."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class IPermissionResolver(Protocol):
    """Resolver de permisos: dado un rol, devuelve sus permisos."""

    def get_permissions_for_role(self, role: str) -> frozenset[str]:
        ...

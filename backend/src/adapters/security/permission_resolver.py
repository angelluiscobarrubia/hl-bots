"""Resolver estático de permisos (mapping en código)."""
from src.core.security.permissions import ROLE_PERMISSIONS


class StaticPermissionResolver:
    """Resuelve permisos contra el mapping estático ROLE_PERMISSIONS."""

    def get_permissions_for_role(self, role: str) -> frozenset[str]:
        return ROLE_PERMISSIONS.get(role, frozenset())


permission_resolver = StaticPermissionResolver()

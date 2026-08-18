"""Permisos y mapping estático rol → permisos."""
from __future__ import annotations


class Perm:
    """Constantes de permisos (evita typos en strings)."""

    USERS_MANAGE = "users:manage"
    ADMIN_PANEL = "admin:panel"
    BOTS_CREATE = "bots:create"
    BOTS_READ = "bots:read"
    BOTS_UPDATE = "bots:update"
    BOTS_DELETE = "bots:delete"
    APIKEYS_MANAGE = "apikeys:manage"
    STRATEGIES_RELOAD = "strategies:reload"


ALL_PERMISSIONS: frozenset[str] = frozenset({
    Perm.USERS_MANAGE,
    Perm.ADMIN_PANEL,
    Perm.BOTS_CREATE,
    Perm.BOTS_READ,
    Perm.BOTS_UPDATE,
    Perm.BOTS_DELETE,
    Perm.APIKEYS_MANAGE,
    Perm.STRATEGIES_RELOAD,
})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": ALL_PERMISSIONS,
    "user": frozenset({
        Perm.BOTS_CREATE,
        Perm.BOTS_READ,
        Perm.BOTS_UPDATE,
        Perm.BOTS_DELETE,
        Perm.APIKEYS_MANAGE,
        Perm.STRATEGIES_RELOAD,
    }),
}

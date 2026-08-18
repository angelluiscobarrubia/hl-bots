"""Tests para el sistema de permisos."""
from src.adapters.security.permission_resolver import permission_resolver
from src.core.ports.i_permission_resolver import IPermissionResolver
from src.core.security.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS, Perm


def test_admin_has_all():
    """admin tiene todos los permisos definidos."""
    assert ROLE_PERMISSIONS["admin"] == ALL_PERMISSIONS
    assert Perm.USERS_MANAGE in ROLE_PERMISSIONS["admin"]
    assert Perm.BOTS_CREATE in ROLE_PERMISSIONS["admin"]


def test_user_permissions():
    """user tiene permisos de bots pero NO users:manage ni admin:panel."""
    user_perms = ROLE_PERMISSIONS["user"]
    assert Perm.BOTS_CREATE in user_perms
    assert Perm.USERS_MANAGE not in user_perms
    assert Perm.ADMIN_PANEL not in user_perms


def test_unknown_role_empty():
    """Un rol desconocido devuelve conjunto vacío."""
    assert permission_resolver.get_permissions_for_role("nobody") == frozenset()


def test_resolver_matches_protocol():
    """StaticPermissionResolver cumple el contrato IPermissionResolver."""
    assert isinstance(permission_resolver, IPermissionResolver)

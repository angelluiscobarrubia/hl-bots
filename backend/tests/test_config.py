"""Tests para la configuración de autenticación y rate limiting."""


def test_auth_settings_defaults():
    """Verifica valores por defecto de settings de auth."""
    from src.core.config import Settings

    s = Settings(_env_file=None)
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 7
    assert s.rate_limit_login_per_minute == 5

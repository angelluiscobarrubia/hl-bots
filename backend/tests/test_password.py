"""Tests para el adaptador de hashing de passwords."""

from src.adapters.security.password import hash_password, verify_password


def test_hash_verify_roundtrip():
    """hash_password produce un hash, y verify_password lo valida."""
    plain = "s3cret"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_wrong_password():
    """verify_password retorna False para una password incorrecta."""
    hashed = hash_password("s3cret")
    assert verify_password("wrong", hashed) is False


def test_hash_is_salted():
    """Argon2 usa sal aleatoria → dos hashes del mismo texto son distintos."""
    assert hash_password("same") != hash_password("same")

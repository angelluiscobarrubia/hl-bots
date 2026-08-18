"""Tests para el cipher Fernet."""

import pytest

from src.adapters.security.cipher import Cipher, CipherError


# Generada una vez para los tests (no es secreta, solo para tests)
TEST_KEY = "t4wB4FFEdWfid9H_FSyHK86s5uSK7GqEgg0uQbBGgb4="


class TestCipherEncryptDecrypt:
    """Tests básicos de encrypt/decrypt."""

    def test_encrypt_decrypt_roundtrip(self):
        """Un string cifrado y descifrado devuelve el original."""
        cipher = Cipher(key=TEST_KEY)
        plaintext = "mi-api-key-secreta-12345"
        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Fernet incluye timestamp + IV aleatorio, así que el ciphertext varía."""
        cipher = Cipher(key=TEST_KEY)
        plaintext = "same-input"
        c1 = cipher.encrypt(plaintext)
        c2 = cipher.encrypt(plaintext)
        assert c1 != c2  # Fernet no es determinista
        # Pero ambos descifran al mismo plaintext
        assert cipher.decrypt(c1) == plaintext
        assert cipher.decrypt(c2) == plaintext

    def test_encrypt_returns_string(self):
        """El resultado de encrypt es str (no bytes), listo para DB."""
        cipher = Cipher(key=TEST_KEY)
        result = cipher.encrypt("test")
        assert isinstance(result, str)

    def test_decrypt_returns_string(self):
        """El resultado de decrypt es str."""
        cipher = Cipher(key=TEST_KEY)
        encrypted = cipher.encrypt("test")
        result = cipher.decrypt(encrypted)
        assert isinstance(result, str)

    def test_encrypt_empty_string(self):
        """Cifrar string vacío funciona (Fernet lo permite)."""
        cipher = Cipher(key=TEST_KEY)
        encrypted = cipher.encrypt("")
        assert cipher.decrypt(encrypted) == ""

    def test_encrypt_unicode(self):
        """Cifra y descifra caracteres unicode correctamente."""
        cipher = Cipher(key=TEST_KEY)
        plaintext = "contraseña-ñ-emoji-🔐"
        encrypted = cipher.encrypt(plaintext)
        assert cipher.decrypt(encrypted) == plaintext


class TestCipherErrors:
    """Tests de manejo de errores."""

    def test_empty_key_raises(self):
        """Clave vacía lanza CipherError."""
        with pytest.raises(CipherError, match="no configurada"):
            Cipher(key="")

    def test_invalid_key_format_raises(self):
        """Clave Fernet malformada lanza CipherError."""
        with pytest.raises(CipherError, match="inválida"):
            Cipher(key="not-a-valid-fernet-key")

    def test_decrypt_invalid_ciphertext_raises(self):
        """Ciphertext alterado o inválido lanza CipherError."""
        cipher = Cipher(key=TEST_KEY)
        with pytest.raises(CipherError, match="inválido"):
            cipher.decrypt("esto-no-es-ciphertext-valido")

    def test_decrypt_with_wrong_key_raises(self):
        """Descifrar con clave incorrecta lanza CipherError."""
        cipher_a = Cipher(key=TEST_KEY)
        other_key = "PHJA7D3L5ZPouXcKfznbTu3ZPXSf7rvdxBuest9LuJs="
        cipher_b = Cipher(key=other_key)
        encrypted = cipher_a.encrypt("secret")
        with pytest.raises(CipherError, match="inválido"):
            cipher_b.decrypt(encrypted)

    def test_encrypt_non_string_raises(self):
        """encrypt() rechaza input que no sea str."""
        cipher = Cipher(key=TEST_KEY)
        with pytest.raises(CipherError, match="debe ser str"):
            cipher.encrypt(12345)  # type: ignore[arg-type]

    def test_decrypt_non_string_raises(self):
        """decrypt() rechaza input que no sea str."""
        cipher = Cipher(key=TEST_KEY)
        with pytest.raises(CipherError, match="debe ser str"):
            cipher.decrypt(b"bytes-not-allowed")  # type: ignore[arg-type]


class TestCipherSingleton:
    """Test del singleton cipher."""

    def test_singleton_uses_settings_key(self, monkeypatch):
        """El singleton usa settings.master_encryption_key por defecto."""
        from src.adapters.security import cipher as cipher_module

        monkeypatch.setattr(
            "src.core.config.settings.master_encryption_key", TEST_KEY
        )
        # Reset singleton para que use la nueva key
        cipher_module._cipher_instance = None
        c = cipher_module.get_cipher()
        encrypted = c.encrypt("test")
        assert c.decrypt(encrypted) == "test"

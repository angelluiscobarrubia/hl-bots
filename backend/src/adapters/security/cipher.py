"""Fernet cipher para cifrado simétrico de secretos (API keys).

Cifra y descifra strings usando AES-128-CBC + HMAC-SHA256 (Fernet).
La clave maestra se carga desde settings.master_encryption_key.

Uso:
    cipher = Cipher()
    encrypted = cipher.encrypt("mi-api-key-secreta")
    plaintext = cipher.decrypt(encrypted)

El ciphertext es base64-urlsafe y puede guardarse en DB de forma segura.
"""

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import settings


class CipherError(Exception):
    """Error al cifrar/descifrar (clave inválida, ciphertext corrupto, etc.)."""


class Cipher:
    """Wrapper sobre Fernet para cifrado simétrico de secretos."""

    def __init__(self, key: str | None = None) -> None:
        """Inicializa con la clave Fernet.

        Args:
            key: Clave Fernet (32 bytes url-safe base64). Si es None, usa
                settings.master_encryption_key.

        Raises:
            CipherError: Si la clave está vacía o es inválida.
        """
        raw = key if key is not None else settings.master_encryption_key
        if not raw:
            raise CipherError(
                "master_encryption_key no configurada. "
                "Genera una con: python -c "
                '"from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        try:
            self._fernet = Fernet(raw.encode())
        except (ValueError, TypeError) as e:
            raise CipherError(f"Clave Fernet inválida: {e}") from e

    def encrypt(self, plaintext: str) -> str:
        """Cifra un string y devuelve el ciphertext base64-urlsafe.

        Args:
            plaintext: Texto plano a cifrar.

        Returns:
            Ciphertext como string base64-urlsafe (seguro para DB).
        """
        if not isinstance(plaintext, str):
            raise CipherError("plaintext debe ser str")
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Descifra un ciphertext Fernet.

        Args:
            ciphertext: Ciphertext base64-urlsafe producido por encrypt().

        Returns:
            Texto plano original.

        Raises:
            CipherError: Si el ciphertext es inválido o fue alterado.
        """
        if not isinstance(ciphertext, str):
            raise CipherError("ciphertext debe ser str")
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("ascii"))
        except InvalidToken as e:
            raise CipherError("Ciphertext inválido o alterado") from e
        return plaintext.decode("utf-8")


# Singleton lazy: no falla al importar si la clave no está configurada.
# Solo falla cuando se usa por primera vez.
_cipher_instance: Cipher | None = None


def get_cipher() -> Cipher:
    """Devuelve el singleton del cipher, creándolo lazily."""
    global _cipher_instance
    if _cipher_instance is None:
        _cipher_instance = Cipher()
    return _cipher_instance

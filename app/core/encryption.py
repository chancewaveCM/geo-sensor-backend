"""Token encryption utilities using Fernet symmetric encryption."""

from cryptography.fernet import Fernet

from app.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption/decryption operations fail."""

    pass


def _get_cipher() -> Fernet:
    """Get configured Fernet cipher instance."""
    if not settings.OAUTH_ENCRYPTION_KEY:
        raise EncryptionError(
            "OAUTH_ENCRYPTION_KEY is not configured. "
            "Generate a key with: python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(settings.OAUTH_ENCRYPTION_KEY.encode())
    except Exception as e:
        raise EncryptionError(f"Invalid OAUTH_ENCRYPTION_KEY: {e}") from e


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a token string.

    Args:
        plaintext: Token to encrypt

    Returns:
        Base64-encoded encrypted token

    Raises:
        EncryptionError: If encryption fails or key is not configured
    """
    try:
        cipher = _get_cipher()
        encrypted = cipher.encrypt(plaintext.encode())
        return encrypted.decode()
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypt a token string.

    Args:
        ciphertext: Base64-encoded encrypted token

    Returns:
        Decrypted token string

    Raises:
        EncryptionError: If decryption fails or key is not configured
    """
    try:
        cipher = _get_cipher()
        decrypted = cipher.decrypt(ciphertext.encode())
        return decrypted.decode()
    except EncryptionError:
        raise
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {e}") from e

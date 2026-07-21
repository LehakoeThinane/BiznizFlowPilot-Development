"""Encrypt/decrypt helpers for tenant-owned secrets stored at rest.

First encrypted-at-rest column in this codebase (Organization.smtp_password_encrypted -
every other secret here, PayFast/Stripe/Resend/SMTP/Agora/R2 keys, is a plain
global environment variable, never a per-tenant DB column). Uses Fernet
(symmetric, authenticated encryption) keyed by
settings.email_credentials_encryption_key.

Key rotation is NOT supported in v1 - rotating the key makes every
already-encrypted value undecryptable. Accepted v1 limitation.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EmailCredentialDecryptionError(Exception):
    """Raised when a stored SMTP password can't be decrypted (wrong/rotated key, corrupt data)."""


@lru_cache
def _fernet() -> Fernet:
    # In dev/staging with no key configured, config.py's _guard_email_credentials_key
    # already warns; generate a process-local key here so encrypt/decrypt still work
    # within a single run (values just won't survive a restart - acceptable locally).
    key = settings.email_credentials_encryption_key or Fernet.generate_key().decode()
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret for storage. Returns ciphertext as a str."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a ciphertext produced by encrypt_secret.

    Raises:
        EmailCredentialDecryptionError: if the ciphertext is invalid, corrupt,
            or was encrypted under a different key.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise EmailCredentialDecryptionError("Stored SMTP password could not be decrypted") from e

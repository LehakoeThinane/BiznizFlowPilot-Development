"""Tests for app/core/crypto.py - the first encrypted-at-rest secret in this codebase."""

from __future__ import annotations

import pytest

from app.core.crypto import EmailCredentialDecryptionError, decrypt_secret, encrypt_secret


def test_encrypt_decrypt_round_trip():
    ciphertext = encrypt_secret("super-secret-smtp-password")
    assert ciphertext != "super-secret-smtp-password"
    assert decrypt_secret(ciphertext) == "super-secret-smtp-password"


def test_ciphertext_is_not_plaintext_substring():
    ciphertext = encrypt_secret("hunter2")
    assert "hunter2" not in ciphertext


def test_decrypting_garbage_raises():
    with pytest.raises(EmailCredentialDecryptionError):
        decrypt_secret("not-a-real-fernet-token")


def test_encrypting_same_value_twice_gives_different_ciphertext():
    """Fernet includes a random IV/timestamp - ciphertexts for identical
    plaintext should differ, but both must still decrypt correctly."""
    a = encrypt_secret("same-value")
    b = encrypt_secret("same-value")
    assert a != b
    assert decrypt_secret(a) == "same-value"
    assert decrypt_secret(b) == "same-value"

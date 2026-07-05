"""Fernet helpers for encrypting persisted secrets."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


def validate_encryption_key() -> None:
    """Ensure LLM_ENCRYPTION_KEY is present and usable by Fernet."""
    _get_fernet()


def _get_key() -> str:
    """Get encryption key from Settings (reads from .env)."""
    from src.core.config import get_settings
    return get_settings().LLM_ENCRYPTION_KEY


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = _get_key()
    if not key:
        raise RuntimeError("LLM_ENCRYPTION_KEY must be set")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("LLM_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_string(value: str) -> str:
    """Encrypt a string for database storage."""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_string(value: str) -> str:
    """Decrypt a database value encrypted by encrypt_string."""
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Encrypted value could not be decrypted") from exc

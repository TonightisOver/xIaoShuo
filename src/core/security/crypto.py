"""Fernet helpers for encrypting persisted secrets."""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


def validate_encryption_key() -> None:
    """Ensure LLM_ENCRYPTION_KEY is present and usable by Fernet."""
    _get_fernet()


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = os.getenv("LLM_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("LLM_ENCRYPTION_KEY must be set")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("LLM_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_string(value: str) -> str:
    """用 Fernet 加密字符串，用于数据库存储。"""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_string(value: str) -> str:
    """解密由 encrypt_string 加密的数据库值。"""
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("无法解密：加密值可能被篡改或使用了不同的密钥") from exc

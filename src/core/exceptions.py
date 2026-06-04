"""Domain-specific exceptions for the xIaoShuo backend."""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Raised when a critical persistence operation fails.

    Callers should treat this as a task-level failure: the requested write did
    not reach durable storage and the upstream generation flow must not be
    considered complete.
    """

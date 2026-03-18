"""Request-scoped context helpers for routing and quota enforcement."""

from __future__ import annotations

from contextvars import ContextVar

_request_user_id: ContextVar[str] = ContextVar("request_user_id", default="system")


def set_request_user_id(user_id: str) -> None:
    """Store request user id in a context variable for downstream services."""
    _request_user_id.set(user_id)


def get_request_user_id() -> str:
    """Get the active request user id, or a stable default for non-request code."""
    return _request_user_id.get()

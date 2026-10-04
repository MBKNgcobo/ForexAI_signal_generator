"""Request-scoped context: correlation IDs for log lines.

A ``contextvar`` carries the current request ID so the JSON log formatter
can attach it to every record emitted while handling that request, without
threading a parameter through every call site.
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("forexai_request_id", default="")


def set_request_id(value: str) -> None:
    """Bind the request ID for the current request context."""

    _request_id.set(value)


def get_request_id() -> str:
    """Return the bound request ID, or ``\"\"`` outside a request."""

    return _request_id.get()

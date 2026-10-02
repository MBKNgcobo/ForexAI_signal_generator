"""Request guards for the HTTP layer."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import expected_api_key


def require_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
) -> None:
    """Require a matching ``X-API-Key`` when one is configured.

    The endpoints behind this dependency trigger paid LLM calls and consume
    external market-data quota. When ``AI_SERVICE_API_KEY`` is not set the
    guard is a no-op so that local development and existing callers are not
    broken; production deployments are expected to set it.
    """

    expected = expected_api_key()

    if expected is None:
        return

    provided = x_api_key or ""

    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-API-Key header is required.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )

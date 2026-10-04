"""Best-effort push delivery for analysis results (P4).

Fire-and-forget ``httpx.post`` with a short timeout; failures are logged,
never raised. The host allowlist (``WEBHOOK_ALLOWLIST``) guards against
SSRF: unset means deny-all, localhost is permitted only for local dev.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from app.config import (
    webhook_allowlist,
    webhook_timeout_seconds,
)

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _host_allowed(
    host: str,
    allowlist: tuple[str, ...],
) -> bool:
    """Exact match, or subdomain match for a wildcard entry.

    ``.example.com`` / ``*.example.com`` cover ``a.example.com``,
    ``a.b.example.com`` and ``example.com``. A bare entry only ever matches
    itself, and a wildcard with no domain (``*``) matches nothing, so the
    list can never widen into "any host".
    """

    for entry in allowlist:
        if entry.startswith("*.") or entry.startswith("."):
            suffix = entry.lstrip("*").lstrip(".")

            if not suffix:
                continue

            if host == suffix or host.endswith(f".{suffix}"):
                return True

        elif host == entry:
            return True

    return False


def webhook_allowed(url: str) -> bool:
    """True when ``url`` is an http(s) URL on an allowlisted host."""

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower()

    if not host:
        return False

    if _host_allowed(host, webhook_allowlist()):
        return True

    # Localhost always allowed so developers can point at a local receiver
    # without editing the allowlist; production deployments set the real
    # hosts and localhost is simply never targeted.
    return host in _LOCAL_HOSTS


async def deliver_webhook(url: str, payload: dict) -> bool:
    """POST ``payload`` to ``url``; False on any failure (never raises)."""

    if not webhook_allowed(url):
        logger.warning(
            "Webhook delivery skipped: host not in WEBHOOK_ALLOWLIST: %s",
            url,
        )
        return False

    try:
        async with httpx.AsyncClient(
            timeout=webhook_timeout_seconds(),
        ) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "Webhook delivery to %s failed: %s: %s",
            url,
            type(exc).__name__,
            exc,
        )
        return False

    return True

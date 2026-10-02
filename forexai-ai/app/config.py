"""Centralised environment configuration.

Historically the service read ``os.getenv`` in many modules and raised at
*import* time when a variable was missing, which meant a container without an
environment file crashed while importing ``app.main``. Everything now goes
through this module so that:

* configuration is read in one place,
* missing configuration produces one clear, actionable message at startup,
* the HTTP layer can degrade gracefully (503) instead of failing to boot.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# Variables required to serve market data and to run the analysis graph.
MARKET_DATA_REQUIRED = ("TWELVE_DATA_API_KEY",)

# Additional variables required by the selected LLM provider.
LLM_REQUIRED = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
    "http": ("LLM_ENDPOINT",),
}


def get_env(name: str, default: str | None = None) -> str | None:
    """Return a stripped environment value, or ``default`` when unset/blank."""

    raw = os.getenv(name)

    if raw is None or not raw.strip():
        return default

    return raw.strip()


def llm_provider_name() -> str:
    return (get_env("LLM_PROVIDER", "openrouter") or "openrouter").lower()


def missing_configuration() -> list[str]:
    """Return the list of required variables that are currently unset."""

    missing = [
        name
        for name in MARKET_DATA_REQUIRED
        if not get_env(name)
    ]

    provider = llm_provider_name()

    for name in LLM_REQUIRED.get(provider, ()):
        if not get_env(name):
            missing.append(name)

    return missing


def log_configuration_status() -> None:
    """Log a single, actionable summary of the configuration state."""

    missing = missing_configuration()

    if not missing:
        logger.info(
            "Configuration OK (LLM provider: %s).",
            llm_provider_name(),
        )
        return

    logger.error(
        "Missing required configuration: %s. "
        "Market data endpoints will return 503 until these are provided. "
        "See .env.example for the full contract.",
        ", ".join(missing),
    )


def configure_logging() -> None:
    """Apply the ``LOG_LEVEL`` default without clobbering installed handlers."""

    level_name = (get_env("LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@lru_cache(maxsize=1)
def cors_origins() -> list[str]:
    """Parse ``CORS_ALLOWED_ORIGIN`` into a list of origins.

    Accepts one or more comma-separated origins. An empty value disables CORS
    entirely, which is the correct default for server-to-server usage.
    """

    raw = get_env("CORS_ALLOWED_ORIGIN", "") or ""

    return [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip()
    ]


@lru_cache(maxsize=1)
def expected_api_key() -> str | None:
    """Optional shared-secret used to protect the expensive endpoints.

    When ``AI_SERVICE_API_KEY`` is unset the guard is disabled, so existing
    local setups and integration clients keep working unchanged.
    """

    return get_env("AI_SERVICE_API_KEY")

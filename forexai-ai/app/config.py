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

from app.observability.logging_config import formatter_for

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


def market_data_provider_name() -> str:
    """Selected market-data channel: ``twelve`` (default) or ``mt5``."""

    return (
        get_env("MARKET_DATA_PROVIDER", "twelve") or "twelve"
    ).lower()


def mt5_dry_run() -> bool:
    """True (default) unless ``MT5_DRY_RUN`` explicitly opts into live.

    Deliberately conservative: any unset/garbage value resolves to
    dry-run, so a deployment can never send real orders just because
    someone typo'd the variable.
    """

    raw = (get_env("MT5_DRY_RUN", "true") or "true").lower()

    return raw not in ("0", "false", "no", "off")


def missing_configuration() -> list[str]:
    """Return the list of required variables that are currently unset."""

    if market_data_provider_name() == "mt5":
        missing = [
            name
            for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
            if not get_env(name)
        ]
    else:
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
    """Apply ``LOG_LEVEL``/``LOG_FORMAT`` without clobbering handlers.

    ``LOG_FORMAT=json`` selects structured JSON lines (with ``request_id``);
    anything else keeps the existing human-readable text format.
    """

    level_name = (get_env("LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = formatter_for(get_env("LOG_FORMAT", "text"))

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(formatter)

        return

    logging.basicConfig(
        level=level,
        format="%(message)s",
    )

    for handler in root.handlers:
        handler.setFormatter(formatter)


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


@lru_cache(maxsize=1)
def analysis_batch_limit() -> int:
    """Max pairs per ``POST /analysis/batch`` (``ANALYSIS_BATCH_LIMIT``).

    Defaults to 10; unparseable or non-positive values fall back to the
    default so a typo degrades safely instead of bricking the endpoint.
    """

    raw = get_env("ANALYSIS_BATCH_LIMIT")

    if raw is None:
        return 10

    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid ANALYSIS_BATCH_LIMIT: %r",
            raw,
        )
        return 10

    return parsed if parsed > 0 else 10


@lru_cache(maxsize=1)
def webhook_allowlist() -> tuple[str, ...]:
    """Hosts permitted as ``webhook_url`` targets (``WEBHOOK_ALLOWLIST``).

    Comma-separated hostnames, compared case-insensitively against the URL
    host. Empty means deny-all: push delivery is opt-in, so a deployment
    that never sets this cannot be turned into an SSRF relay.

    An entry may be a wildcard, written ``.example.com`` or
    ``*.example.com``, to cover every subdomain (and the bare domain). That
    exists for ephemeral receivers whose hostname cannot be enumerated in a
    static list - a Cloudflare quick tunnel is a new random subdomain on
    every restart. Bare entries stay exact, and ``*`` on its own matches
    nothing, so widening the list is always an explicit decision.
    """

    raw = get_env("WEBHOOK_ALLOWLIST", "") or ""

    return tuple(
        host.strip().lower()
        for host in raw.split(",")
        if host.strip()
    )


#: Push delivery is fire-and-forget; the default keeps a slow receiver from
#: holding the analysis response open.
DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 3.0


@lru_cache(maxsize=1)
def webhook_timeout_seconds() -> float:
    """Per-request timeout for webhook delivery (``WEBHOOK_TIMEOUT_SECONDS``).

    Tunnelled receivers (a laptop running the MT5 bridge) can be slower than
    a local one, so the ceiling is configurable. Non-numeric, zero and
    negative values fall back to the default rather than disabling the guard.
    """

    raw = get_env(
        "WEBHOOK_TIMEOUT_SECONDS",
        str(DEFAULT_WEBHOOK_TIMEOUT_SECONDS),
    )

    try:
        parsed = float(raw) if raw else DEFAULT_WEBHOOK_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid WEBHOOK_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_WEBHOOK_TIMEOUT_SECONDS

    if parsed <= 0:
        logger.warning(
            "Ignoring non-positive WEBHOOK_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_WEBHOOK_TIMEOUT_SECONDS

    return parsed


# ---------------------------------------------------------------------------
# Quant ensemble membership and weighting.
#
# Defaults live here so a deployment can drop a model or rebalance the
# ensemble through the environment without a rebuild. The weights do not need
# to sum to 1 - ``EnsembleQuantModel`` normalises them.
# ---------------------------------------------------------------------------

DEFAULT_ENSEMBLE_MODELS = (
    "random_forest",
    "xgboost",
    "logistic_regression",
)


DEFAULT_ENSEMBLE_WEIGHTS = {
    "random_forest": 0.4,
    "xgboost": 0.4,
    "logistic_regression": 0.2,
}


@lru_cache(maxsize=1)
def ensemble_models() -> tuple[str, ...]:
    """Names of the quant models to load, in order.

    ``ENSEMBLE_MODELS`` accepts a comma-separated list. Unknown names are
    ignored so a typo cannot silently enable a model that is not registered.
    An empty or fully-invalid value falls back to the default membership.
    """

    raw = get_env("ENSEMBLE_MODELS")

    if raw is None:
        return DEFAULT_ENSEMBLE_MODELS

    requested = [
        name.strip()
        for name in raw.split(",")
        if name.strip()
    ]

    models = tuple(
        name
        for name in requested
        if name in DEFAULT_ENSEMBLE_WEIGHTS
    )

    return models or DEFAULT_ENSEMBLE_MODELS


@lru_cache(maxsize=1)
def ensemble_weights() -> dict[str, float]:
    """Per-model weights parsed from ``ENSEMBLE_WEIGHTS``.

    Format: ``random_forest=0.4,xgboost=0.4,logistic_regression=0.2``. Only
    registered names are kept and malformed entries keep their default, so a
    typo degrades to the safe configuration rather than a crash.
    """

    weights = dict(DEFAULT_ENSEMBLE_WEIGHTS)

    raw = get_env("ENSEMBLE_WEIGHTS")

    if not raw:
        return weights

    for pair in raw.split(","):
        name, _, value = pair.partition("=")

        name = name.strip()
        value = value.strip()

        if not name or not value:
            continue

        try:
            parsed = float(value)

        except ValueError:
            logger.warning(
                "Ignoring invalid ENSEMBLE_WEIGHTS entry: %r",
                pair.strip(),
            )
            continue

        if name in weights and parsed > 0:
            weights[name] = parsed

    return weights

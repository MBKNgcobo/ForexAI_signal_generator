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

    Phase 1 (SQA C-01 hardening): a bare ``*`` is rejected. It would open
    the paid endpoints to any website; list each dashboard origin
    explicitly instead.
    """

    raw = get_env("CORS_ALLOWED_ORIGIN", "") or ""

    origins = [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip()
    ]

    return [
        origin
        for origin in origins
        if origin != "*"
    ]


@lru_cache(maxsize=1)
def is_production() -> bool:
    """True when ``ENV``/``ENVIRONMENT`` explicitly selects production.

    Phase 1 (SQA C-01): security defaults must be fail-closed in hosted
    deployments while staying frictionless for local development. Only the
    explicit values ``production``/``prod`` opt into the strict defaults;
    anything else (including unset) keeps the local behaviour.
    """

    raw = (
        get_env("ENV", "")
        or get_env("ENVIRONMENT", "")
        or ""
    )

    return raw.strip().lower() in {
        "production",
        "prod",
    }


@lru_cache(maxsize=1)
def expected_api_key() -> str | None:
    """Optional shared-secret used to protect the expensive endpoints.

    When ``AI_SERVICE_API_KEY`` is unset the guard is disabled, so existing
    local setups and integration clients keep working unchanged. In
    production (see ``is_production``) a missing key is a deployment error:
    the value is still returned as ``None`` so callers can map it to 503,
    and the request is never served open.
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


#: Wall-clock budget for one /analysis call. A slow RAG store + two LLM
#: calls + provider fetch previously held a worker with no bound.
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 120.0


@lru_cache(maxsize=1)
def analysis_timeout_seconds() -> float:
    """Total budget for one analysis request (``ANALYSIS_TIMEOUT_SECONDS``).

    Phase 2: expiry maps to 503 (degraded dependency) so the caller
    retries instead of hanging. Invalid values fall back to the default.
    """

    raw = get_env(
        "ANALYSIS_TIMEOUT_SECONDS",
        str(DEFAULT_ANALYSIS_TIMEOUT_SECONDS),
    )

    try:
        parsed = float(raw) if raw else DEFAULT_ANALYSIS_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid ANALYSIS_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_ANALYSIS_TIMEOUT_SECONDS

    if parsed <= 0:
        logger.warning(
            "Ignoring non-positive ANALYSIS_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_ANALYSIS_TIMEOUT_SECONDS

    return parsed


#: Per-source budget for fundamental refreshes. Sequential unbounded
#: refreshes previously added seconds to p95.
DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS = 8.0


@lru_cache(maxsize=1)
def fundamental_refresh_timeout_seconds() -> float:
    """Per-source refresh budget (``FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS``).

    Phase 2 (SQA C-06): each World Bank / SOTW / Business Quant refresh
    runs concurrently under this timeout; expiry degrades to cached RAG
    evidence. Invalid values fall back to the default.
    """

    raw = get_env(
        "FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS",
        str(DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS),
    )

    try:
        parsed = (
            float(raw)
            if raw
            else DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS
        )
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS

    if parsed <= 0:
        logger.warning(
            "Ignoring non-positive FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS: %r",
            raw,
        )
        return DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS

    return parsed


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

DEFAULT_RAG_DB_SSLMODE = "require"


@lru_cache(maxsize=1)
def rag_db_sslmode() -> str:
    """TLS mode for the fundamentals RAG store (``RAG_DB_SSLMODE``).

    Defaults to "require" because every deployment that matters connects to
    a managed database across a network that refuses plaintext. libpq's
    default is "prefer", which attempts an unencrypted handshake first and is
    rejected by Neon with "connection is insecure (try using
    sslmode=require)". A local ``docker compose`` Postgres has no such
    requirement, so the value stays overridable and can be set to "disable"
    there rather than weakening the default everywhere.
    """
    return (
        get_env("RAG_DB_SSLMODE", DEFAULT_RAG_DB_SSLMODE)
        or DEFAULT_RAG_DB_SSLMODE
    )


@lru_cache(maxsize=1)
def rag_db_hostaddr() -> str | None:
    """Optional pinned IP for the RAG store (``RAG_DB_HOSTADDR``).

    Managed providers usually publish AAAA records alongside A records.
    Free-tier hosts have no IPv6 route, so psycopg walks the unreachable
    addresses first and only succeeds over IPv4, delaying every cold start.
    Pinning one address skips that. Unset by default so DNS stays in charge.
    """
    return get_env("RAG_DB_HOSTADDR", "") or None


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


DEFAULT_QUANT_PROBABILITY_THRESHOLD = 0.50


@lru_cache(maxsize=1)
def quant_threshold() -> float:
    """Minimum quant probability for LOW risk and the opposing-quant veto.

    ``QUANT_PROBABILITY_THRESHOLD`` overrides the default. Validation
    (EURUSD 15m, 113 days, net of spread=0.00015 + slippage=0.00005 per
    round trip — see app/backtesting/threshold_analysis.py) is the basis:
    0.60 admitted ~0.7 candidates/day with a negative net; 0.50 admitted
    ~5.9/day with the only profitable net. Out-of-range or malformed
    values fall back to the default so a typo can never silently disable
    the veto (0.0) or block every trade (1.0+).
    """

    raw = get_env("QUANT_PROBABILITY_THRESHOLD")

    if raw is None:
        return DEFAULT_QUANT_PROBABILITY_THRESHOLD

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid QUANT_PROBABILITY_THRESHOLD=%r, using %.2f",
            raw,
            DEFAULT_QUANT_PROBABILITY_THRESHOLD,
        )
        return DEFAULT_QUANT_PROBABILITY_THRESHOLD

    if not 0.0 < parsed < 1.0:
        logger.warning(
            "Ignoring out-of-range QUANT_PROBABILITY_THRESHOLD=%r, using %.2f",
            raw,
            DEFAULT_QUANT_PROBABILITY_THRESHOLD,
        )
        return DEFAULT_QUANT_PROBABILITY_THRESHOLD

    return parsed


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


# ---------------------------------------------------------------------------
# Trading mode, safety rails and paper trading (recommendation implementation).
#
# Fail-safe defaults: the service starts in DRY_RUN; caps that could surprise
# an operator are either small and sane (3 open positions) or explicitly
# opt-in (0 = disabled for money-based limits). Every malformed value
# degrades to the safe default rather than crashing or disabling a guard.
# ---------------------------------------------------------------------------

TRADING_MODE_DRY_RUN = "dry_run"
TRADING_MODE_PAPER = "paper"
TRADING_MODE_MT5 = "mt5"
_TRADING_MODES = frozenset(
    {TRADING_MODE_DRY_RUN, TRADING_MODE_PAPER, TRADING_MODE_MT5}
)


@lru_cache(maxsize=1)
def trading_mode() -> str:
    """Execution mode selected by ``TRADING_MODE`` (default ``dry_run``).

    ``dry_run``: log payloads, never send (today's behaviour).
    ``paper``: fill against live market data in a virtual account.
    ``mt5``: real terminal orders — still gated by the dual-key interlock
    (``--live`` + ``MT5_DRY_RUN=false``) in the bridge.
    Unknown values fall back to ``dry_run`` so a typo can never arm
    real trading.
    """

    raw = (get_env("TRADING_MODE", TRADING_MODE_DRY_RUN) or TRADING_MODE_DRY_RUN)
    raw = raw.strip().lower().replace("-", "_")

    if raw not in _TRADING_MODES:
        logger.warning(
            "Ignoring invalid TRADING_MODE=%r, using %r.",
            raw,
            TRADING_MODE_DRY_RUN,
        )
        return TRADING_MODE_DRY_RUN

    return raw


@lru_cache(maxsize=1)
def max_open_positions() -> int:
    """Simultaneous open-position cap (``MAX_OPEN_POSITIONS``, default 3).

    A small default keeps supervised testing comfortable while still
    stopping a duplicate-signal storm. ``0`` disables the cap.
    """

    raw = get_env("MAX_OPEN_POSITIONS", "3") or "3"

    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid MAX_OPEN_POSITIONS=%r, using 3.", raw
        )
        return 3

    if parsed < 0:
        logger.warning(
            "Ignoring negative MAX_OPEN_POSITIONS=%d, using 3.", parsed
        )
        return 3

    return parsed


@lru_cache(maxsize=1)
def max_daily_loss() -> float:
    """Daily-loss circuit breaker in account currency (``MAX_DAILY_LOSS``).

    ``<= 0`` (the default) disables the breaker; a positive value trips
    the bridge when equity falls that far below the first equity of the
    UTC day. Invalid input falls back to disabled.
    """

    raw = get_env("MAX_DAILY_LOSS")

    if raw is None:
        return 0.0

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid MAX_DAILY_LOSS=%r, breaker disabled.", raw
        )
        return 0.0

    return parsed if parsed > 0 else 0.0


@lru_cache(maxsize=1)
def duplicate_window_seconds() -> float:
    """Idempotency window (``DUPLICATE_WINDOW_SECONDS``, default 300).

    A second signal for the same symbol+direction inside the window is
    refused. ``0`` disables the duplicate guard.
    """

    raw = get_env("DUPLICATE_WINDOW_SECONDS", "300") or "300"

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid DUPLICATE_WINDOW_SECONDS=%r, using 300.", raw
        )
        return 300.0

    return parsed if parsed >= 0 else 300.0


@lru_cache(maxsize=1)
def risk_percent() -> float:
    """Balance risk per trade in percent (``RISK_PERCENT``, default 0).

    ``0`` (disabled) keeps the fixed ``MT5_SIGNAL_VOLUME`` behaviour.
    Values above 10 are clamped — risking more than 10% per trade is
    never sensible and usually a unit mistake.
    """

    raw = get_env("RISK_PERCENT")

    if raw is None:
        return 0.0

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid RISK_PERCENT=%r, sizing disabled.", raw
        )
        return 0.0

    if parsed <= 0:
        return 0.0

    if parsed > 10.0:
        logger.warning(
            "Clamping RISK_PERCENT=%.2f to 10.0 per trade.", parsed
        )
        return 10.0

    return parsed


@lru_cache(maxsize=1)
def max_spread_pips() -> float:
    """Refuse entries when the spread exceeds this many pips.

    ``0`` (default) disables the gate. Invalid values fall back to off.
    """

    raw = get_env("MAX_SPREAD_PIPS")

    if raw is None:
        return 0.0

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid MAX_SPREAD_PIPS=%r, gate disabled.", raw
        )
        return 0.0

    return parsed if parsed > 0 else 0.0


@lru_cache(maxsize=1)
def mt5_allow_live() -> bool:
    """``MT5_ALLOW_LIVE`` (default false): hard block on non-demo accounts.

    Fail-closed: anything except an explicit enable keeps the block.
    """

    raw = (get_env("MT5_ALLOW_LIVE", "false") or "false").lower()
    return raw in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def trade_log_path() -> str:
    """JSONL trade/signal log location (``TRADE_LOG_PATH``)."""

    return get_env("TRADE_LOG_PATH", "data/trade_log.jsonl") or (
        "data/trade_log.jsonl"
    )


@lru_cache(maxsize=1)
def stop_file_path() -> str:
    """Kill-switch file (``TRADING_STOP_FILE``); presence blocks all sends."""

    return get_env("TRADING_STOP_FILE", "data/TRADING_STOP") or (
        "data/TRADING_STOP"
    )


@lru_cache(maxsize=1)
def paper_initial_balance() -> float:
    """Starting virtual balance (``PAPER_INITIAL_BALANCE``, default 10000)."""

    raw = get_env("PAPER_INITIAL_BALANCE", "10000") or "10000"

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid PAPER_INITIAL_BALANCE=%r, using 10000.", raw
        )
        return 10000.0

    return parsed if parsed > 0 else 10000.0


@lru_cache(maxsize=1)
def paper_poll_seconds() -> float:
    """SL/TP monitor interval for paper positions (default 60 s, min 5 s)."""

    raw = get_env("PAPER_POLL_SECONDS", "60") or "60"

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid PAPER_POLL_SECONDS=%r, using 60.", raw
        )
        return 60.0

    return parsed if parsed >= 5.0 else 5.0


@lru_cache(maxsize=1)
def paper_spread_pips() -> float:
    """Spread charged once at paper entry (default 1.5 pips, matching the
    backtest's 0.00015). Negative or invalid falls back to the default."""

    raw = get_env("PAPER_SPREAD_PIPS", "1.5") or "1.5"

    try:
        parsed = float(raw)
    except ValueError:
        logger.warning(
            "Ignoring invalid PAPER_SPREAD_PIPS=%r, using 1.5.", raw
        )
        return 1.5

    return parsed if parsed >= 0 else 1.5


@lru_cache(maxsize=1)
def paper_state_path() -> str:
    """Persisted virtual account file (``PAPER_STATE_PATH``)."""

    return get_env("PAPER_STATE_PATH", "data/paper_account.json") or (
        "data/paper_account.json"
    )


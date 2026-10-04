"""Single factory for the configured market-data provider.

Both construction sites (the LangGraph ``market_data_agent`` and the
HTTP ``/market-data`` route) previously hardcoded TwelveData. This
module makes the channel selectable through ``MARKET_DATA_PROVIDER``
while keeping the original contract: misconfiguration raises a
``RuntimeError`` with one actionable message, which callers turn into
503s — never an import-time crash.
"""

from __future__ import annotations

from app.broker.mt5_market_data_provider import MT5MarketDataProvider
from app.config import get_env, market_data_provider_name
from app.services.market_data_provider import (
    MarketDataProvider,
)
from app.services.twelve_data_market_data_provider import (
    TwelveDataMarketDataProvider,
)


def create_market_data_provider() -> MarketDataProvider:
    """Build the provider selected by ``MARKET_DATA_PROVIDER``.

    ``mt5``: requires ``MT5_LOGIN``/``MT5_PASSWORD``/``MT5_SERVER``
    (the terminal connects lazily on first query, so construction
    itself never touches the terminal).

    ``twelve`` (default): requires ``TWELVE_DATA_API_KEY``.
    """

    name = market_data_provider_name()

    if name == "mt5":
        login = get_env("MT5_LOGIN")
        password = get_env("MT5_PASSWORD")
        server = get_env("MT5_SERVER")

        missing = [
            var
            for var, value in (
                ("MT5_LOGIN", login),
                ("MT5_PASSWORD", password),
                ("MT5_SERVER", server),
            )
            if not value
        ]

        if missing:
            raise RuntimeError(
                "MARKET_DATA_PROVIDER=mt5 requires: "
                + ", ".join(missing)
                + ". See .env.example for the MT5 configuration block."
            )

        raw_timeout = get_env("MT5_TIMEOUT_SECONDS", "60") or "60"

        try:
            timeout = float(raw_timeout)
        except ValueError:
            timeout = 60.0

        return MT5MarketDataProvider(
            login=int(login or 0),
            password=password or "",
            server=server or "",
            path=get_env("MT5_PATH"),
            timeout_seconds=timeout,
        )

    if name in ("twelve", "twelvedata", "twelve_data"):
        api_key = get_env("TWELVE_DATA_API_KEY")

        if not api_key:
            raise RuntimeError(
                "TWELVE_DATA_API_KEY is not configured. "
                "See .env.example for the required configuration."
            )

        return TwelveDataMarketDataProvider(api_key=api_key)

    raise RuntimeError(
        f"Unknown MARKET_DATA_PROVIDER: {name!r}. "
        "Expected 'twelve' or 'mt5'."
    )

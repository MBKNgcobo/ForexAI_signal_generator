"""MT5 market-data provider (Phase 2).

Implements the project's ``MarketDataProvider`` ABC against a local
MetaTrader 5 terminal, so MT5 sits alongside ``TwelveData`` behind the
same interface the LangGraph agents already consume.

Key contracts:
- ``get_market_data`` maps our ``Timeframe`` names to MT5 constants,
  fetches OHLCV via ``copy_rates_from_pos``, and serializes each record
  into the frozen ``Candle`` schema (UTC ISO-8601 timestamps).
- MT5 rate timestamps are broker-clock epoch seconds; they are
  defensively converted with ``datetime.fromtimestamp(t, tz=UTC)`` so
  downstream agents always see UTC regardless of the broker's server
  timezone (EET/GMT+2/GMT+3).
- Broker symbol suffixes (``EURUSD.m``, ``EURUSD+``) are resolved
  internally; the returned ``MarketData.symbol`` stays the requested
  one so the HTTP contract is unchanged.
- ``MetaTrader5`` is imported lazily inside each method (never at
  module scope) so Linux/Docker imports and the hermetic test suite
  keep working without the Windows-only package.
- Any ``None``/failure from an MT5 query raises ``MT5DataError`` (a
  ``RuntimeError`` subclass, so the existing HTTP layer maps it to 503)
  carrying ``mt5.last_error()`` retcodes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.broker.mt5_connection import (
    MT5ConnectionError,
    connect,
    shutdown,
)
from app.schemas.market import Candle, MarketData
from app.services.market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


class MT5DataError(RuntimeError):
    """An MT5 data query failed (None result or terminal retcode)."""


@dataclass(frozen=True)
class MT5Tick:
    """Latest tick snapshot normalized to UTC."""

    time: datetime
    bid: float
    ask: float
    last: float | None
    volume: float | None


@dataclass(frozen=True)
class MT5Depth:
    """Order-book depth split into bid/ask price levels."""

    bids: list[tuple[float, float]]  # (price, volume)
    asks: list[tuple[float, float]]  # (price, volume)


class MT5MarketDataProvider(MarketDataProvider):
    """Serve candles (plus optional tick/depth helpers) from MT5."""

    # Our Timeframe names -> MetaTrader5 constant attribute names.
    # Resolved with getattr at call time because the package is lazy.
    TIMEFRAME_ATTRS = {
        "OneMinute": "TIMEFRAME_M1",
        "FiveMinutes": "TIMEFRAME_M5",
        "FifteenMinutes": "TIMEFRAME_M15",
        "OneHour": "TIMEFRAME_H1",
        "FourHours": "TIMEFRAME_H4",
        "OneDay": "TIMEFRAME_D1",
    }

    def __init__(
        self,
        login: int | None,
        password: str,
        server: str,
        path: str | None = None,
        timeout_seconds: float = 60.0,
    ):
        # ``login=None`` attaches to an open, logged-in terminal session
        # (see mt5_connection.connect); the factory always passes real
        # credentials for unattended service use.
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.timeout_seconds = timeout_seconds
        self._connected = False

    # -- connection -------------------------------------------------------

    def _ensure_connected(self) -> Any:
        """Connect once on first use; returns the mt5 module."""

        if not self._connected:
            try:
                connect(
                    login=self.login,
                    password=self.password,
                    server=self.server,
                    path=self.path,
                    timeout_seconds=self.timeout_seconds,
                )
            except MT5ConnectionError as exc:
                raise MT5DataError(
                    f"MT5 market-data connection failed: {exc}"
                ) from exc
            self._connected = True

        from app.broker.mt5_connection import _import_mt5

        return _import_mt5()

    # -- helpers ----------------------------------------------------------

    def _mt5_timeframe(self, mt5: Any, timeframe: str) -> int:
        attr = self.TIMEFRAME_ATTRS.get(timeframe)

        if attr is None:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}"
            )

        return int(getattr(mt5, attr))

    @staticmethod
    def _resolve_symbol(mt5: Any, symbol: str) -> str:
        """Return the broker's symbol name for our bare ``symbol``.

        Brokers suffix demo symbols (``EURUSD.m``, ``EURUSD+``); exact
        matches win, otherwise the shortest prefix match is chosen so
        ``EURUSD`` resolves deterministically regardless of suffix.
        """

        info = mt5.symbol_info(symbol)

        if info is not None:
            return symbol

        candidates = mt5.symbols_get(symbol) or []

        matches = [
            str(s.name)
            for s in candidates
            if str(s.name).upper().startswith(symbol.upper())
        ]

        if not matches:
            raise MT5DataError(
                f"Symbol {symbol!r} not found in the MT5 terminal "
                f"(suffix variants also exhausted). "
                f"last_error={mt5.last_error()}"
            )

        resolved = min(matches, key=len)

        mt5.symbol_select(resolved, True)

        logger.debug(
            "MT5 symbol %s resolved to broker symbol %s.",
            symbol,
            resolved,
        )

        return resolved

    @staticmethod
    def _rate_to_candle(row: Any) -> Candle | None:
        """Serialize one numpy/dict rate record into a ``Candle``.

        ``row['time']`` is broker-clock epoch seconds; converted
        defensively to UTC. Inconsistent rows (possible on a forming
        candle) are skipped rather than failing the whole series.
        """

        try:
            ts = datetime.fromtimestamp(
                int(row["time"]), tz=timezone.utc
            ).isoformat()

            candle = Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["tick_volume"]),
            )
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Skipping malformed MT5 rate row: %s", exc)
            return None

        return candle

    # -- MarketDataProvider ABC -------------------------------------------

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:

        mt5 = self._ensure_connected()
        mt5_timeframe = self._mt5_timeframe(mt5, timeframe)
        broker_symbol = self._resolve_symbol(mt5, symbol)

        try:
            rates = mt5.copy_rates_from_pos(
                broker_symbol,
                mt5_timeframe,
                0,
                int(limit),
            )
        except Exception as exc:
            raise MT5DataError(
                f"copy_rates_from_pos raised "
                f"{type(exc).__name__}: {exc}. "
                f"last_error={mt5.last_error()}"
            ) from exc

        if rates is None or len(rates) == 0:
            raise MT5DataError(
                f"copy_rates_from_pos returned no rates for "
                f"{broker_symbol} ({timeframe}). "
                f"last_error={mt5.last_error()}"
            )

        candles: list[Candle] = []
        seen: set = set()

        # MT5 returns oldest-first; re-sort defensively so the schema's
        # strictly-ascending validator can never be tripped by broker
        # output quirks or duplicate forming-candle rows.
        for row in sorted(rates, key=lambda r: int(r["time"])):
            candle = self._rate_to_candle(row)

            if candle is None or candle.timestamp in seen:
                continue

            seen.add(candle.timestamp)
            candles.append(candle)

        if not candles:
            raise MT5DataError(
                f"All MT5 rate rows for {broker_symbol} were malformed. "
                f"last_error={mt5.last_error()}"
            )

        return MarketData(
            symbol=symbol,  # requested name, not the broker's suffix
            timeframe=timeframe,
            candles=candles,
        )

    # -- optional extras (not part of the ABC) ----------------------------

    def get_tick(self, symbol: str) -> MT5Tick:
        """Latest tick for ``symbol``; raises ``MT5DataError`` on None."""

        mt5 = self._ensure_connected()
        broker_symbol = self._resolve_symbol(mt5, symbol)

        tick = mt5.symbol_info_tick(broker_symbol)

        if tick is None:
            raise MT5DataError(
                f"symbol_info_tick returned None for {broker_symbol}. "
                f"last_error={mt5.last_error()}"
            )

        return MT5Tick(
            time=datetime.fromtimestamp(
                int(tick.time), tz=timezone.utc
            ),
            bid=float(tick.bid),
            ask=float(tick.ask),
            last=float(tick.last) if getattr(tick, "last", None) else None,
            volume=(
                float(tick.volume)
                if getattr(tick, "volume", None) is not None
                else None
            ),
        )

    def get_depth(self, symbol: str) -> MT5Depth:
        """Market-book depth; adds the symbol to the book if needed."""

        mt5 = self._ensure_connected()
        broker_symbol = self._resolve_symbol(mt5, symbol)

        book = mt5.market_book_get(broker_symbol)

        if book is None:
            # Some terminals require an explicit market_book_add first.
            mt5.market_book_add(broker_symbol)
            book = mt5.market_book_get(broker_symbol)

        if book is None:
            raise MT5DataError(
                f"market_book_get returned None for {broker_symbol} "
                f"(depth may be unsupported for this symbol). "
                f"last_error={mt5.last_error()}"
            )

        buy_types = {
            int(getattr(mt5, "BOOK_TYPE_BUY", 1)),
            int(getattr(mt5, "BOOK_TYPE_BUY_MARKET", 3)),
        }

        bids: list[tuple[float, float]] = []
        asks: list[tuple[float, float]] = []

        for level in book:
            entry = (float(level.price), float(level.volume))

            if int(level.type) in buy_types:
                bids.append(entry)
            else:
                asks.append(entry)

        return MT5Depth(bids=bids, asks=asks)

    def close(self) -> None:
        """Release the IPC handle (``shutdown`` is safe to call)."""

        shutdown()
        self._connected = False




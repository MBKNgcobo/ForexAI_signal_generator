import asyncio
import logging
from datetime import datetime, timezone

from app.observability.metrics import record_cache_lookup
from app.schemas.market import MarketData

from app.services.market_data_cache import (
    TIMEFRAME_BAR_SECONDS,
    MarketDataCache,
    detect_candle_gap_seconds,
    max_candle_age_seconds,
)
from app.services.market_data_provider import (
    MarketDataProvider,
)

logger = logging.getLogger(__name__)


class MarketDataService:

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: MarketDataCache,
    ):
        self.provider = provider
        self.cache = cache
        # Phase 1 (SQA C-07): per-key asyncio locks for single-flight
        # fetches. Concurrent misses for the same symbol/timeframe/limit
        # previously each triggered a provider call (quota burn); now the
        # first fetches while the rest await the same result.
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._key_locks.get(key)

            if lock is None:
                lock = asyncio.Lock()
                self._key_locks[key] = lock

            return lock

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:

        cache_key = (
            f"{symbol.upper()}:"
            f"{timeframe}:"
            f"{limit}"
        )

        lock = await self._lock_for(cache_key)

        async with lock:
            cached_data = self.cache.get(cache_key)

            if cached_data is not None:
                logger.debug(
                    "Market data cache HIT: %s",
                    cache_key,
                )
                record_cache_lookup(hit=True)

                return cached_data

            logger.debug(
                "Market data cache MISS: %s",
                cache_key,
            )
            record_cache_lookup(hit=False)

            data = await self.provider.get_market_data(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )

            self._validate_freshness(data)

            self.cache.set(
                cache_key,
                data,
            )

            return data

    def _validate_freshness(self, data: MarketData) -> None:
        """Fail closed on stale feeds and missing-candle gaps (SQA C-03).

        A delayed, duplicated, or gapped feed must never silently produce a
        BUY/SELL. Staleness (newest candle older than two bars + budget)
        and gaps (>1.5 bars between consecutive candles) raise RuntimeError
        so the HTTP layer maps them to 503 with Retry-After.
        """

        candles = data.candles

        if not candles:
            raise RuntimeError(
                f"Market data for {data.symbol} {data.timeframe} "
                "contains no candles."
            )

        last = candles[-1]
        last_ts = getattr(last, "timestamp", None)

        if isinstance(last_ts, str):
            try:
                last_ts = datetime.fromisoformat(last_ts)
            except ValueError:
                last_ts = None

        if isinstance(last_ts, datetime):
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)

            age = (
                datetime.now(timezone.utc) - last_ts
            ).total_seconds()

            budget = max_candle_age_seconds(data.timeframe)

            if age > budget:
                raise RuntimeError(
                    f"Market data for {data.symbol} {data.timeframe} "
                    f"is stale: newest candle is {age:.0f}s old "
                    f"(budget {budget}s). Please retry shortly."
                )

        gap = detect_candle_gap_seconds(candles, data.timeframe)
        bar = TIMEFRAME_BAR_SECONDS.get(data.timeframe)

        if gap is not None and bar is not None and gap > bar * 1.5:
            raise RuntimeError(
                f"Market data for {data.symbol} {data.timeframe} "
                f"has a {gap:.0f}s gap between candles "
                f"(expected ~{bar}s). Please retry shortly."
            )
"""TTL behaviour of the candle cache.

The cache is what stops the analysis graph from hammering the provider within a
request burst, so HIT/MISS and expiry are pinned directly.
"""

from datetime import datetime, timedelta, timezone

import app.services.market_data_cache as cache_module
from app.schemas.market import Candle, MarketData
from app.services.market_data_cache import MarketDataCache
from app.services.market_data_provider_factory import (
    get_shared_market_data_service,
    reset_shared_market_data_service,
)


def _market_data() -> MarketData:
    return MarketData(
        symbol="EURUSD",
        timeframe="FifteenMinutes",
        candles=[
            Candle(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=1.1,
                high=1.2,
                low=1.0,
                close=1.15,
                volume=1.0,
            )
        ],
    )


def test_set_then_get_returns_cached_value():
    cache = MarketDataCache(ttl_seconds=30)

    cache.set("key", _market_data())

    assert cache.get("key") is not None


def test_missing_key_returns_none():
    assert MarketDataCache().get("absent") is None


def test_entry_expires_after_ttl(monkeypatch):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = {"value": base}

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now["value"]

    monkeypatch.setattr(cache_module, "datetime", FrozenDatetime)

    cache = MarketDataCache(ttl_seconds=30)
    cache.set("key", _market_data())

    now["value"] = base + timedelta(seconds=29)
    assert cache.get("key") is not None

    now["value"] = base + timedelta(seconds=31)
    assert cache.get("key") is None


def test_clear_empties_the_cache():
    cache = MarketDataCache()
    cache.set("key", _market_data())

    cache.clear()

    assert cache.get("key") is None


def test_graph_and_route_share_one_service_instance(monkeypatch):
    """Phase 2 SQA: graph agent + HTTP route warm/read the same cache.

    Previously each built its own provider+cache, so identical symbols
    fetched twice never hit. Both must now resolve to the same object.
    """
    from app.agents import market_data_agent
    from app.api import market_data as market_data_route

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "twelve")
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "dummy")
    reset_shared_market_data_service()
    market_data_agent.get_market_data_service.cache_clear()
    market_data_route.build_market_data_service.cache_clear()

    try:
        via_graph = market_data_agent.get_market_data_service()
        via_route = market_data_route.build_market_data_service()

        assert via_graph is via_route
        assert via_graph.cache is via_route.cache
    finally:
        reset_shared_market_data_service()
        market_data_agent.get_market_data_service.cache_clear()
        market_data_route.build_market_data_service.cache_clear()


def test_shared_service_single_flight_under_concurrency(monkeypatch):
    """Two concurrent first-requests build exactly one service (T-11)."""
    import asyncio

    from app.agents import market_data_agent

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "twelve")
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "dummy")
    reset_shared_market_data_service()
    market_data_agent.get_market_data_service.cache_clear()

    try:
        async def _build():
            return await asyncio.to_thread(get_shared_market_data_service)

        async def _main():
            return await asyncio.gather(*(_build() for _ in range(8)))

        instances = asyncio.run(_main())

        assert all(instance is instances[0] for instance in instances)
    finally:
        reset_shared_market_data_service()
        market_data_agent.get_market_data_service.cache_clear()

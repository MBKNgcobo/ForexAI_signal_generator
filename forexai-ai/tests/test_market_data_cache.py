"""TTL behaviour of the candle cache.

The cache is what stops the analysis graph from hammering the provider within a
request burst, so HIT/MISS and expiry are pinned directly.
"""

from datetime import datetime, timedelta, timezone

import app.services.market_data_cache as cache_module
from app.schemas.market import Candle, MarketData
from app.services.market_data_cache import MarketDataCache


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

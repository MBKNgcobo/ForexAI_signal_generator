from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.schemas.market import MarketData


#: Expected bar length per timeframe, used by the staleness/gap gate
#: (Phase 1, SQA C-03). Values are nominal wall-clock durations.
TIMEFRAME_BAR_SECONDS: dict[str, int] = {
    "OneMinute": 60,
    "FiveMinutes": 5 * 60,
    "FifteenMinutes": 15 * 60,
    "OneHour": 60 * 60,
    "FourHours": 4 * 60 * 60,
    "OneDay": 24 * 60 * 60,
}


def max_candle_age_seconds(timeframe: str) -> int:
    """Oldest acceptable age of the newest candle for ``timeframe``.

    Allows two full bars plus a small provider-delay budget so a healthy
    feed passes while a delayed/stale feed fails closed. Unknown
    timeframes fall back to 15 minutes rather than disabling the gate.
    """

    bar = TIMEFRAME_BAR_SECONDS.get(timeframe, 15 * 60)

    return bar * 2 + 60


def detect_candle_gap_seconds(
    candles,
    timeframe: str,
) -> float | None:
    """Largest internal gap (seconds) between consecutive candles.

    Returns ``None`` when fewer than two candles exist or timestamps are
    unusable. A gap larger than ~1.5 bars means a missing candle, which
    invalidates EMA/RSI/ATR continuity.
    """

    if candles is None or len(candles) < 2:
        return None

    try:
        stamps = [
            candle.timestamp
            if hasattr(candle, "timestamp")
            else candle.get("timestamp")
            for candle in candles
        ]
    except Exception:
        return None

    try:
        moments = [
            stamp
            if isinstance(stamp, datetime)
            else datetime.fromisoformat(str(stamp))
            for stamp in stamps
        ]
    except Exception:
        return None

    gaps = [
        (later - earlier).total_seconds()
        for earlier, later in zip(moments, moments[1:])
    ]

    if not gaps:
        return None

    return max(gaps)


@dataclass
class CacheEntry:
    data: MarketData
    expires_at: datetime


class MarketDataCache:

    def __init__(self, ttl_seconds: int = 30):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[MarketData]:
        entry = self._cache.get(key)

        if entry is None:
            return None

        now = datetime.now(timezone.utc)

        if now >= entry.expires_at:
            del self._cache[key]
            return None

        return entry.data

    def set(
        self,
        key: str,
        data: MarketData,
    ) -> None:
        now = datetime.now(timezone.utc)

        self._cache[key] = CacheEntry(
            data=data,
            expires_at=now + self.ttl,
        )

    def clear(self) -> None:
        self._cache.clear()
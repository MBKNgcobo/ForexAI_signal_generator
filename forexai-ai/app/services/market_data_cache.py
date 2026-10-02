from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.schemas.market import MarketData


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
from app.schemas.market import MarketData

from app.services.market_data_cache import MarketDataCache
from app.services.market_data_provider import (
    MarketDataProvider,
)

class MarketDataService:

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: MarketDataCache,
    ):
        self.provider = provider
        self.cache = cache

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

        cached_data = self.cache.get(cache_key)

        if cached_data is not None:
            print(
                f"Market data cache HIT: {cache_key}"
            )

            return cached_data

        print(
            f"Market data cache MISS: {cache_key}"
        )

        data = await self.provider.get_market_data(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        self.cache.set(
            cache_key,
            data,
        )

        return data
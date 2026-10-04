import logging

from app.observability.metrics import record_cache_lookup
from app.schemas.market import MarketData

from app.services.market_data_cache import MarketDataCache
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

        self.cache.set(
            cache_key,
            data,
        )

        return data
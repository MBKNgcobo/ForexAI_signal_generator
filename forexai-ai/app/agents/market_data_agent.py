import logging
from functools import lru_cache

from dotenv import load_dotenv

from app.services.market_data_service import MarketDataService
from app.services.market_data_provider_factory import (
    create_market_data_provider,
)
from app.services.market_data_cache import MarketDataCache

load_dotenv()

logger = logging.getLogger(__name__)

AI_ANALYSIS_CANDLE_LIMIT = 300


@lru_cache(maxsize=1)
def get_market_data_service() -> MarketDataService:
    """Build the provider on first use instead of at import time.

    The previous module-level construction raised RuntimeError when
    TWELVE_DATA_API_KEY was unset, which crashed the container while it was
    still importing app.main. Deferring construction lets the service boot;
    callers get a clear error only when market data is actually requested.

    The concrete channel (TwelveData or local MT5) comes from
    ``MARKET_DATA_PROVIDER`` via the shared factory.
    """

    provider = create_market_data_provider()

    return MarketDataService(
        provider=provider,
        cache=MarketDataCache(ttl_seconds=30),
    )

async def run_market_data_agent(
    state: dict,
) -> dict:

    symbol = state["symbol"]
    timeframe = state["timeframe"]

    market_data_service = get_market_data_service()

    market_data = (
        await market_data_service.get_market_data(
            symbol=symbol,
            timeframe=timeframe,
            limit=AI_ANALYSIS_CANDLE_LIMIT,
        )
    )

    logger.info(
        "Market Data Agent: %s %s retrieved %d candles",
        symbol,
        timeframe,
        len(market_data.candles),
    )

    return {
        "market_data": [
            candle.model_dump()
            for candle in market_data.candles
        ]
    }
import logging
from functools import lru_cache

from dotenv import load_dotenv

from app.services.market_data_service import MarketDataService
from app.services.market_data_provider_factory import (
    get_shared_market_data_service,
)

load_dotenv()

logger = logging.getLogger(__name__)

AI_ANALYSIS_CANDLE_LIMIT = 300


@lru_cache(maxsize=1)
def get_market_data_service() -> MarketDataService:
    """Process-wide service shared with the HTTP route (Phase 2 SQA).

    Previously this built a private provider+cache, so graph fetches never
    warmed the route cache and vice versa. Now delegates to the shared
    factory instance. The lru_cache wrapper is kept so existing imports and
    test patches keep working; reset via the factory's reset helper.
    """

    return get_shared_market_data_service()

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
from functools import lru_cache

from dotenv import load_dotenv

from app.services.market_data_service import MarketDataService
from app.services.twelve_data_market_data_provider import (
    TwelveDataMarketDataProvider,
)
from app.services.market_data_cache import MarketDataCache

load_dotenv()

AI_ANALYSIS_CANDLE_LIMIT = 300


@lru_cache(maxsize=1)
def get_market_data_service() -> MarketDataService:
    """Build the provider on first use instead of at import time.

    The previous module-level construction raised RuntimeError when
    TWELVE_DATA_API_KEY was unset, which crashed the container while it was
    still importing app.main. Deferring construction lets the service boot;
    callers get a clear error only when market data is actually requested.
    """

    import os

    api_key = os.getenv("TWELVE_DATA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not configured."
        )

    provider = TwelveDataMarketDataProvider(
        api_key=api_key
    )

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

    print(
    f"Market Data Agent: "
    f"{symbol} {timeframe} "
    f"retrieved {len(market_data.candles)} candles"
)
    return {
        "market_data": [
            candle.model_dump()
            for candle in market_data.candles
        ]
    }
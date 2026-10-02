import pytest

from app.services.market_data_service import (
    MarketDataService,
)

from app.services.market_data_cache import (
    MarketDataCache,
)

from app.services.mock_market_data_provider import (
    MockMarketDataProvider,
)


@pytest.mark.asyncio
async def test_market_data_service_returns_candles():

    provider = MockMarketDataProvider()
    cache = MarketDataCache()

    service = MarketDataService(
        provider,
        cache,
    )

    result = await service.get_market_data(
        symbol="EURUSD",
        timeframe="FourHours",
        limit=50,
    )

    assert result.symbol == "EURUSD"
    assert result.timeframe == "FourHours"

    assert len(result.candles) == 50

    assert result.candles[0].open > 0
    assert result.candles[0].close > 0
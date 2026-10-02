from app.schemas.market import Candle, MarketData

from app.services.market_data_provider import (
    MarketDataProvider,
)


class MockMarketDataProvider(MarketDataProvider):

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:

        candles = []

        price = 1.1000

        for i in range(limit):

            open_price = price
            close_price = price + 0.001

            high_price = (
                close_price + 0.0005
            )

            low_price = (
                open_price - 0.0005
            )

            candles.append(
                Candle(
                    timestamp=str(i),
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=1000,
                )
            )

            price = close_price

        return MarketData(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
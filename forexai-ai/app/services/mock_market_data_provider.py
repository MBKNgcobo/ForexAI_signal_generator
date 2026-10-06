from datetime import datetime, timedelta, timezone

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

        # Phase 1 (SQA C-03): the freshness gate requires recent,
        # gap-free candles. Emit bars ending at the last closed boundary
        # (one bar step) so the mock satisfies the same contract as a
        # healthy provider. Falls back to 1-hour steps for unknown
        # timeframes.
        try:
            from app.services.market_data_cache import (
                TIMEFRAME_BAR_SECONDS,
            )

            step = TIMEFRAME_BAR_SECONDS.get(timeframe, 3600)
        except Exception:
            step = 3600

        newest = (
            datetime.now(timezone.utc) - timedelta(seconds=step)
        ).replace(microsecond=0)

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
                    timestamp=(
                        newest - timedelta(seconds=step * (limit - 1 - i))
                    ),
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
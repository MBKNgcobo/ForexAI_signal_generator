from abc import ABC, abstractmethod

from app.schemas.market import MarketData


class MarketDataProvider(ABC):

    @abstractmethod
    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:
        pass
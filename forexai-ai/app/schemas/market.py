from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Timeframe(StrEnum):
    """Timeframes the market-data provider can serve.

    Defined once so the HTTP layer, the graph state and the provider's
    interval map cannot drift apart.
    """

    ONE_MINUTE = "OneMinute"
    FIVE_MINUTES = "FiveMinutes"
    FIFTEEN_MINUTES = "FifteenMinutes"
    ONE_HOUR = "OneHour"
    FOUR_HOURS = "FourHours"
    ONE_DAY = "OneDay"


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: AwareDatetime
    open: float = Field(allow_inf_nan=False)
    high: float = Field(allow_inf_nan=False)
    low: float = Field(allow_inf_nan=False)
    close: float = Field(allow_inf_nan=False)
    volume: float | None = None

    @model_validator(mode="after")
    def _ohlc_is_consistent(self):
        if not (self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high):
            raise ValueError("inconsistent OHLC")
        return self

class MarketData(BaseModel):
    symbol: str
    timeframe: str
    candles: list[Candle]

    @model_validator(mode="after")
    def _strictly_ascending(self):
        ts = [c.timestamp for c in self.candles]
        if any(a >= b for a, b in zip(ts, ts[1:])):
            raise ValueError("candles must be strictly ascending by timestamp")
        return self
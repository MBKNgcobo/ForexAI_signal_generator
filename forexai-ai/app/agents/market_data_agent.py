import logging
from datetime import datetime, timezone
from functools import lru_cache

from dotenv import load_dotenv

from app.services.market_data_cache import TIMEFRAME_BAR_SECONDS
from app.services.market_data_service import MarketDataService
from app.services.market_data_provider_factory import (
    get_shared_market_data_service,
)

load_dotenv()

logger = logging.getLogger(__name__)

AI_ANALYSIS_CANDLE_LIMIT = 300

#: Minimum closed bars the quant path needs (EMA200 + RSI14 + MACD +
#: ATR14 + rolling-20). Fewer than this and the feature frame has no
#: fully-valid row; fail closed instead of predicting on NaNs.
MIN_CLOSED_CANDLES = 210


def drop_forming_candle(candles: list, timeframe: str) -> list:
    """Exclude the still-forming bar so indicators never see it (SQA C-03).

    A candle whose timestamp is at or after the current bar boundary is
    in-progress: its close/high/low will still move. Using it leaks the
    intra-bar price into EMA/RSI/ATR and the quant feature row. The raw
    ``/market-data`` route still returns it; only the analysis graph
    filters it here.
    """

    if not candles:
        return candles

    bar = TIMEFRAME_BAR_SECONDS.get(timeframe)

    if not bar:
        return candles

    last = candles[-1]
    last_ts = last.get("timestamp") if isinstance(last, dict) else getattr(
        last, "timestamp", None
    )

    if isinstance(last_ts, str):
        try:
            last_ts = datetime.fromisoformat(last_ts)
        except ValueError:
            return candles

    if not isinstance(last_ts, datetime):
        return candles

    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    boundary = datetime.fromtimestamp(
        int(now.timestamp()) // bar * bar, tz=timezone.utc
    )

    if last_ts >= boundary:
        return candles[:-1]

    return candles


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

    closed = [
        candle.model_dump()
        for candle in market_data.candles
    ]

    closed = drop_forming_candle(closed, timeframe)

    if len(closed) < MIN_CLOSED_CANDLES:
        raise RuntimeError(
            f"Not enough closed candles for {symbol} {timeframe}: "
            f"{len(closed)} available, {MIN_CLOSED_CANDLES} required. "
            "Please retry shortly."
        )

    logger.info(
        "Market Data Agent: %s %s retrieved %d candles (%d closed)",
        symbol,
        timeframe,
        len(market_data.candles),
        len(closed),
    )

    return {
        "market_data": closed
    }
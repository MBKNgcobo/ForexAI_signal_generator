from functools import lru_cache

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.security import require_api_key
from app.config import get_env
from app.schemas.market import Timeframe
from app.services.market_data_service import MarketDataService
from app.services.twelve_data_market_data_provider import (
    TwelveDataMarketDataProvider,
)
from app.services.market_data_cache import MarketDataCache

load_dotenv()

router = APIRouter(
    prefix="/market-data",
    tags=["Market Data"],
    dependencies=[Depends(require_api_key)],
)


@lru_cache(maxsize=1)
def build_market_data_service() -> MarketDataService:
    """Construct the provider on first request and reuse it.

    This used to run at import time and raised RuntimeError when the API key
    was absent, so a container started without an environment file could not
    even import the application. Missing credentials now surface as a 503 on
    the endpoint that needs them.

    The result is memoised so the 30-second candle cache survives across
    requests. ``lru_cache`` does not store exceptions, so a missing key keeps
    returning 503 instead of poisoning the cache.
    """

    api_key = get_env("TWELVE_DATA_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "TWELVE_DATA_API_KEY is not configured. "
                "See .env.example for the required configuration."
            ),
            headers={"Retry-After": "30"},
        )

    return MarketDataService(
        TwelveDataMarketDataProvider(api_key=api_key),
        MarketDataCache(ttl_seconds=30),
    )


@router.get("/{symbol}")
async def get_market_data(
    symbol: str = Path(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z]{6}$",
        description="Six-letter currency symbol, e.g. EURUSD.",
    ),
    timeframe: Timeframe = Query(
        default=Timeframe.FIFTEEN_MINUTES
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    market_data_service = build_market_data_service()

    try:
        return await market_data_service.get_market_data(
            symbol=symbol.upper(),
            timeframe=timeframe.value,
            limit=limit,
        )
    except ValueError as exc:
        # Provider-level rejections (unsupported timeframe, no values
        # returned) are bad requests, not server faults.
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        # Provider surfaces quota exhaustion / upstream errors this way.
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "30"},
        ) from exc
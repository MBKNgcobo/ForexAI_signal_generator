from functools import lru_cache

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.security import require_api_key
from app.schemas.market import Timeframe
from app.services.market_data_service import MarketDataService
from app.services.market_data_provider_factory import (
    get_shared_market_data_service,
)

load_dotenv()

router = APIRouter(
    prefix="/market-data",
    tags=["Market Data"],
    dependencies=[Depends(require_api_key)],
)


@lru_cache(maxsize=1)
def build_market_data_service() -> MarketDataService:
    """Process-wide service shared with the analysis graph (Phase 2 SQA).

    Previously the route built its own provider+cache while the graph agent
    built another, so identical symbols fetched twice warmed two caches.
    Now both delegate to the shared factory instance; missing credentials
    still surface as 503 on the endpoint that needs them.

    ``lru_cache`` does not store exceptions, so a missing key keeps
    returning 503 instead of poisoning the cache.
    """

    try:
        return get_shared_market_data_service()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "30"},
        ) from exc


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
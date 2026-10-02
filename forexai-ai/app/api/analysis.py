from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_api_key
from app.fundamentals.currency_map import split_forex_symbol
from app.schemas.analysis import (
    AnalyzeMarketRequest,
)

from app.schemas.ai_response import (
    AiAnalysisResponse,
)

from app.services.ai_response_mapper import (
    AnalysisIncompleteError,
    map_graph_result_to_response,
)

from app.services.forex_analysis_service import (
    ForexAnalysisService,
)

from app.llm.llm_errors import (
    LLMUnavailableError,
)

from app.llm.llm_factory import (
    create_llm_provider,
)


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
    dependencies=[Depends(require_api_key)],
)


@lru_cache(maxsize=1)
def get_analysis_service() -> ForexAnalysisService:
    """Build the analysis graph on first use.

    Constructing this at import time connects to Postgres (the RAG store),
    which stops the whole service from booting when the database is not
    available. Deferring it keeps /health and /market-data usable.
    """

    llm_provider = create_llm_provider()

    return ForexAnalysisService(
        llm_provider
    )


@router.post(
    "",
    response_model=AiAnalysisResponse,
)
async def analyze(
    request: AnalyzeMarketRequest,
):

    # Fail fast on an unsupported pair. Without this the ValueError was
    # raised deep inside the fundamental agent, after market data had been
    # fetched, and escaped as a 500.
    try:
        split_forex_symbol(request.symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    try:
        analysis_service = get_analysis_service()
    except RuntimeError as exc:
        # Missing configuration (LLM key / provider settings) or an
        # unreachable RAG store must not masquerade as an internal crash.
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "30"},
        ) from exc

    try:

        result = await analysis_service.analyze(
            request.symbol,
            request.timeframe,
        )

    except LLMUnavailableError as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "AI provider is rate-limited or unavailable. "
                "Please retry shortly."
            ),
            headers={"Retry-After": "30"},
        ) from exc

    except ValueError as exc:
        # An LLM response that cannot be parsed/validated. The upstream model
        # produced unusable output, so this is a gateway-level failure.
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI provider returned an unusable response. "
                "Please retry shortly."
            ),
        ) from exc

    try:
        return map_graph_result_to_response(
            result
        )
    except AnalysisIncompleteError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
import asyncio
import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_api_key
from app.config import analysis_batch_limit
from app.fundamentals.currency_map import split_forex_symbol
from app.llm.llm_errors import (
    LLMUnavailableError,
)
from app.llm.llm_factory import (
    create_llm_provider,
)
from app.schemas.ai_response import (
    AiAnalysisResponse,
)
from app.schemas.analysis import (
    AnalyzeMarketRequest,
    BatchAnalysisResponse,
    BatchAnalyzeMarketRequest,
    BatchItemError,
)
from app.services.ai_response_mapper import (
    AnalysisIncompleteError,
    map_graph_result_to_response,
)
from app.services.forex_analysis_service import (
    ForexAnalysisService,
)
from app.services.webhook_delivery import deliver_webhook

logger = logging.getLogger(__name__)


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

    except RuntimeError as exc:
        # Market-data outages surface as RuntimeError (quota, upstream
        # errors, no candles). Without this they escape as a bare 500.
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "30"},
        ) from exc

    except Exception as exc:
        # Anything else is a genuine internal failure. Log it with context
        # so the 500 detail stays opaque to callers but debuggable in logs.
        logger.exception(
            "Analysis failed for %s %s: %s: %s",
            request.symbol,
            request.timeframe,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Analysis failed due to an internal error.",
        ) from exc

    try:
        response = map_graph_result_to_response(
            result
        )
    except AnalysisIncompleteError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    if request.webhook_url:
        # Same best-effort contract as the batch route: a push failure is
        # logged, never raised, so the caller still gets its signal.
        await deliver_webhook(
            request.webhook_url,
            response.model_dump(mode="json"),
        )

    return response


async def _analyze_one(
    index: int,
    item: AnalyzeMarketRequest,
    semaphore: asyncio.Semaphore | None = None,
) -> AiAnalysisResponse | BatchItemError:
    """Analyse one batch item; failures become per-item errors, not 500s."""

    async def _run() -> AiAnalysisResponse | BatchItemError:
        return await _analyze_one_inner(index, item)

    if semaphore is None:
        return await _run()

    async with semaphore:
        return await _run()


async def _analyze_one_inner(
    index: int,
    item: AnalyzeMarketRequest,
) -> AiAnalysisResponse | BatchItemError:
    """Single-item pipeline shared by the batch route (semaphore outside)."""

    try:
        split_forex_symbol(item.symbol)
    except ValueError as exc:
        return BatchItemError(
            index=index,
            status=400,
            detail=str(exc),
        )

    try:
        analysis_service = get_analysis_service()
    except RuntimeError as exc:
        return BatchItemError(
            index=index,
            status=503,
            detail=str(exc),
        )

    try:
        result = await analysis_service.analyze(
            item.symbol,
            item.timeframe,
        )
    except LLMUnavailableError as exc:
        return BatchItemError(
            index=index,
            status=503,
            detail=(
                "AI provider is rate-limited or unavailable. "
                f"Please retry shortly. ({exc})"
            ),
        )
    except ValueError as exc:
        return BatchItemError(
            index=index,
            status=502,
            detail=(
                "The AI provider returned an unusable response. "
                f"Please retry shortly. ({exc})"
            ),
        )
    except RuntimeError as exc:
        return BatchItemError(
            index=index,
            status=503,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception(
            "Batch item %d (%s %s) failed: %s: %s",
            index,
            item.symbol,
            item.timeframe,
            type(exc).__name__,
            exc,
        )
        return BatchItemError(
            index=index,
            status=500,
            detail="Analysis failed due to an internal error.",
        )

    try:
        return map_graph_result_to_response(result)
    except AnalysisIncompleteError as exc:
        return BatchItemError(
            index=index,
            status=502,
            detail=str(exc),
        )


@router.post(
    "/batch",
    response_model=BatchAnalysisResponse,
)
async def analyze_batch(
    request: BatchAnalyzeMarketRequest,
):
    """Analyse up to ``ANALYSIS_BATCH_LIMIT`` pairs in one call.

    Items run concurrently via ``asyncio.gather`` over the same path as
    ``POST /analysis``; each item's failure is captured per-item so one bad
    pair never fails the whole batch. Concurrency is bounded (Phase 2 SQA):
    at most 3 items run at once so a 10-pair batch cannot burst 10× LLM +
    provider + RAG calls and trip every quota at once.
    """

    limit = analysis_batch_limit()

    if len(request.requests) > limit:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Batch too large: {len(request.requests)} requests, "
                f"limit is {limit}. Split the batch or raise "
                "ANALYSIS_BATCH_LIMIT."
            ),
        )

    semaphore = asyncio.Semaphore(3)

    outcomes = await asyncio.gather(
        *(
            _analyze_one(index, item, semaphore)
            for index, item in enumerate(request.requests)
        )
    )

    response = BatchAnalysisResponse(
        results=[
            outcome
            for outcome in outcomes
            if isinstance(outcome, AiAnalysisResponse)
        ],
        errors=[
            outcome
            for outcome in outcomes
            if isinstance(outcome, BatchItemError)
        ],
    )

    if request.webhook_url:
        # Best-effort push; delivery failure is logged, never raised.
        await deliver_webhook(
            request.webhook_url,
            response.model_dump(mode="json"),
        )

    return response
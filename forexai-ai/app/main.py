from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.analysis import router as analysis_router
from app.api.market_data import router as market_data_router
from app.config import (
    configure_logging,
    cors_origins,
    log_configuration_status,
    missing_configuration,
)
from app.observability.context import set_request_id
from app.observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration once, without preventing /health from serving.

    Failing at import time (the previous behaviour) made the whole container
    crash when an environment variable was missing. Logging the problem and
    continuing keeps /health useful for orchestrators while the dependent
    endpoints return 503 with a clear message.
    """

    configure_logging()
    log_configuration_status()

    yield


app = FastAPI(
    title="ForexAI AI Service",
    version="1.0.0",
    lifespan=lifespan,
)


_origins = cors_origins()

if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def request_id_and_metrics_middleware(request: Request, call_next):
    """Bind a request ID and record Prometheus HTTP metrics.

    The ID is honoured from ``X-Request-ID`` when a caller supplies one
    (useful for tracing across the C# API), otherwise generated. The
    route template is used for metric labels so per-symbol traffic cannot
    explode cardinality.
    """

    request_id = request.headers.get("x-request-id") or uuid4().hex[:16]
    set_request_id(request_id)

    started_at = perf_counter()

    response = await call_next(request)

    elapsed = perf_counter() - started_at

    try:
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
    except Exception:
        path = request.url.path

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        path=path,
        status=str(response.status_code),
    ).inc()

    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=request.method,
        path=path,
    ).observe(elapsed)

    response.headers["X-Request-ID"] = request_id

    return response


@app.get("/health")
async def health():
    """Liveness probe. Always 200 while the process can serve HTTP.

    It intentionally does not fail when configuration is missing: an
    orchestrator should be able to tell "the process is up" apart from "the
    dependencies are ready" (see ``/ready``).
    """

    return {
        "status": "ForexAI AI Service is running",
        "service": app.title,
        "version": app.version,
    }


@app.get("/ready")
async def ready():
    """Readiness probe: 200 only when every required variable is configured.

    Missing configuration does not crash the process (fail-soft by design), so
    a plain liveness check cannot report it. This endpoint surfaces the gap so
    a load balancer can hold traffic back until the service is fully usable.
    """

    missing = missing_configuration()

    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "Service is running but required configuration is missing: "
                + ", ".join(missing)
            ),
            headers={"Retry-After": "30"},
        )

    return {"status": "ready"}


@app.get("/version")
async def version():
    """Build metadata for dashboards and deploy checks."""

    return {
        "service": app.title,
        "version": app.version,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint (public by default, as is standard)."""

    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


app.include_router(analysis_router)
app.include_router(market_data_router)

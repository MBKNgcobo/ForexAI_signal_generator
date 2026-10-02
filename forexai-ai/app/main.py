from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.market_data import router as market_data_router
from app.config import (
    configure_logging,
    cors_origins,
    log_configuration_status,
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


@app.get("/health")
async def health():
    return {
        "status": "ForexAI AI Service is running"
    }


app.include_router(analysis_router)
app.include_router(market_data_router)

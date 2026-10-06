"""Observability package: request IDs, structured logs, Prometheus metrics."""

from app.observability.context import get_request_id, set_request_id
from app.observability.logging_config import JsonFormatter, formatter_for
from app.observability.metrics import (
    GRAPH_NODE_DURATION_SECONDS,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    LLM_FAILURES_TOTAL,
    LLM_REQUESTS_TOTAL,
    MARKET_DATA_CACHE_TOTAL,
    record_cache_lookup,
    record_cache_negative_hit,
    record_llm_failure,
    record_llm_request,
)

__all__ = [
    "GRAPH_NODE_DURATION_SECONDS",
    "HTTP_REQUEST_DURATION_SECONDS",
    "HTTP_REQUESTS_TOTAL",
    "LLM_FAILURES_TOTAL",
    "LLM_REQUESTS_TOTAL",
    "MARKET_DATA_CACHE_TOTAL",
    "JsonFormatter",
    "formatter_for",
    "get_request_id",
    "record_cache_lookup",
    "record_cache_negative_hit",
    "record_llm_failure",
    "record_llm_request",
    "set_request_id",
]

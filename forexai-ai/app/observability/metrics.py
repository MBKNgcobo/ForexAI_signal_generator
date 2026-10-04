"""Prometheus metrics for the service.

Counters and histograms only (no gauges), with low-cardinality labels: the
HTTP middleware records the *templated* route path (``/analysis``) rather
than raw URLs so per-symbol traffic cannot explode label cardinality.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "forexai_http_requests_total",
    "HTTP requests served, by method, route and status code.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "forexai_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)

GRAPH_NODE_DURATION_SECONDS = Histogram(
    "forexai_graph_node_duration_seconds",
    "LangGraph node execution time in seconds.",
    ["node"],
)

LLM_FAILURES_TOTAL = Counter(
    "forexai_llm_failures_total",
    "LLM calls that failed (typed provider errors).",
    ["provider", "error"],
)

MARKET_DATA_CACHE_TOTAL = Counter(
    "forexai_market_data_cache_total",
    "Market-data cache lookups, by outcome.",
    ["result"],
)


def record_cache_lookup(*, hit: bool) -> None:
    """Increment the cache HIT/MISS counter (safe to call from services)."""

    MARKET_DATA_CACHE_TOTAL.labels(
        result="hit" if hit else "miss",
    ).inc()


def record_llm_failure(provider: str, error: str) -> None:
    """Increment the LLM failure counter with a bounded error label."""

    LLM_FAILURES_TOTAL.labels(
        provider=provider,
        error=error,
    ).inc()

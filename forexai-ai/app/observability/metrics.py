"""Prometheus metrics for the service.

Counters and histograms only (no gauges), with low-cardinality labels: the
HTTP middleware records the *templated* route path (``/analysis``) rather
than raw URLs so per-symbol traffic cannot explode label cardinality.
LLM success/failure counters carry only the provider name and a bounded
error class (never model IDs, prompts, or raw messages) for the same
reason.
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

LLM_REQUESTS_TOTAL = Counter(
    "forexai_llm_requests_total",
    "LLM completions requested, by provider and outcome.",
    ["provider", "outcome"],
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


def record_cache_negative_hit() -> None:
    """Increment the counter for a negative-cache (known outage) hit."""

    MARKET_DATA_CACHE_TOTAL.labels(result="negative").inc()


def _bounded_error_label(error: str) -> str:
    """Map a raw error string to a low-cardinality failure class."""

    lowered = (error or "").lower()

    if "rate" in lowered or "429" in lowered:
        return "rate_limited"
    if "timeout" in lowered or "deadline" in lowered:
        return "timeout"
    if "connect" in lowered:
        return "connection"
    if "auth" in lowered or "401" in lowered or "403" in lowered:
        return "auth"
    if "empty" in lowered or "no completion" in lowered:
        return "empty_completion"
    if "parse" in lowered or "json" in lowered or "unusable" in lowered:
        return "unusable_output"
    if "unavailable" in lowered or "503" in lowered or "500" in lowered:
        return "unavailable"

    return "other"


def record_llm_request(provider: str, *, success: bool) -> None:
    """Increment the LLM request counter by outcome (success/failure)."""

    LLM_REQUESTS_TOTAL.labels(
        provider=provider,
        outcome="success" if success else "failure",
    ).inc()


def record_llm_failure(provider: str, error: str) -> None:
    """Increment the LLM failure counter with a bounded error label."""

    LLM_FAILURES_TOTAL.labels(
        provider=provider,
        error=_bounded_error_label(error),
    ).inc()


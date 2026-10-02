"""Retry, model cycling and 503 behaviour for the OpenRouter provider.

OpenRouter's free models are served from shared pools that throttle with
429s, so these tests pin the retry/cycling contract that keeps a single
throttled response from turning into a 500 for the client.
"""

import asyncio

import openai
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# openai 3.x vendors its HTTP client as ``httpx2``; the exception classes
# require a real response object, so the helper below builds one.
import httpx2

from app.api.analysis import router as analysis_router
from app.llm.llm_errors import LLMUnavailableError
from app.llm.openrouter_provider import OpenRouterProvider


class _StubMessage:
    def __init__(self, content):
        self.content = content


class _StubChoice:
    def __init__(self, content):
        self.message = _StubMessage(content)


class _StubResponse:
    def __init__(self, content):
        self.choices = [_StubChoice(content)]


class _StubCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.models = []

    async def create(self, **kwargs):
        self.models.append(kwargs["model"])

        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


class _StubClient:
    def __init__(self, outcomes):
        self.completions = _StubCompletions(outcomes)
        self.chat = type(
            "StubChat",
            (),
            {"completions": self.completions},
        )()


def _build_provider(
    outcomes,
    fallbacks=("fallback-model",),
) -> OpenRouterProvider:

    provider = OpenRouterProvider(
        api_key="test-key",
        model="primary-model",
        fallback_models=list(fallbacks),
    )

    provider.client = _StubClient(outcomes)

    return provider


def _status_error(
    error_class,
    status_code: int,
    retry_after: str | None = None,
):
    request = httpx2.Request(
        "POST",
        "https://openrouter.ai/api/v1/chat/completions",
    )

    headers = (
        {"retry-after": retry_after}
        if retry_after is not None
        else {}
    )

    response = httpx2.Response(
        status_code,
        request=request,
        headers=headers,
    )

    return error_class(
        "simulated failure",
        response=response,
        body=None,
    )


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch):
    """Capture retry delays instead of actually sleeping."""

    delays: list[float] = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    return delays


@pytest.mark.asyncio
async def test_retries_transient_rate_limit_then_succeeds():

    provider = _build_provider(
        [
            _status_error(openai.RateLimitError, 429),
            _StubResponse("OK"),
        ]
    )

    result = await provider.generate("system", "user")

    assert result == "OK"

    assert provider.client.completions.models == [
        "primary-model",
        "primary-model",
    ]


@pytest.mark.asyncio
async def test_non_retryable_error_moves_to_next_model():

    provider = _build_provider(
        [
            _status_error(openai.AuthenticationError, 401),
            _StubResponse("OK"),
        ]
    )

    result = await provider.generate("system", "user")

    assert result == "OK"

    # 401 is not worth retrying, so the fallback is tried immediately.
    assert provider.client.completions.models == [
        "primary-model",
        "fallback-model",
    ]


@pytest.mark.asyncio
async def test_empty_completion_is_retried():

    provider = _build_provider(
        [
            _StubResponse("   "),
            _StubResponse("OK"),
        ]
    )

    assert await provider.generate("system", "user") == "OK"

    assert provider.client.completions.models == [
        "primary-model",
        "primary-model",
    ]


@pytest.mark.asyncio
async def test_raises_llm_unavailable_when_all_models_fail():

    provider = _build_provider(
        [
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.RateLimitError, 429),
        ]
    )

    with pytest.raises(LLMUnavailableError) as excinfo:
        await provider.generate("system", "user")

    # Existing callers expect a RuntimeError.
    assert isinstance(excinfo.value, RuntimeError)

    # Two models, three attempts each.
    assert provider.client.completions.models == [
        "primary-model",
        "primary-model",
        "primary-model",
        "fallback-model",
        "fallback-model",
        "fallback-model",
    ]


@pytest.mark.asyncio
async def test_honours_retry_after_header(no_backoff_sleep):

    provider = _build_provider(
        [
            _status_error(
                openai.RateLimitError,
                429,
                retry_after="7",
            ),
            _StubResponse("OK"),
        ]
    )

    await provider.generate("system", "user")

    assert no_backoff_sleep

    assert no_backoff_sleep[0] >= 7.0


class _FailingAnalysisService:

    async def analyze(
        self,
        symbol: str,
        timeframe: str,
    ):
        raise LLMUnavailableError(
            "all configured models are rate-limited"
        )


def test_analysis_endpoint_returns_503_when_llm_unavailable(
    monkeypatch,
):

    monkeypatch.setattr(
        "app.api.analysis.get_analysis_service",
        lambda: _FailingAnalysisService(),
    )

    app = FastAPI()
    app.include_router(analysis_router)

    client = TestClient(app)

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "11111111-1111-1111-1111-111111111111",
            "symbol": "EURUSD",
            "timeframe": "FifteenMinutes",
        },
    )

    assert response.status_code == 503

    assert (
        "rate-limited"
        in response.json()["detail"].lower()
    )

    assert response.headers.get("retry-after") == "30"

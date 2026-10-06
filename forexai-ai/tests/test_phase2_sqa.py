"""Phase 2 (SQA quality) regression tests.

* C-05 — transient malformed LLM JSON recovers via one parse-retry;
  persistent garbage still surfaces as ValueError (502 at the API layer).
* C-06 — fundamental refreshes run concurrently under a timeout (a slow
  source degrades to cache instead of stalling); intraday prompts carry
  the stale-annual-data recency note.
* C-08 — non-numeric MT5_LOGIN / MT5_TIMEOUT_SECONDS raise RuntimeError
  (503 contract), never ValueError (500).
* Timeouts — ANALYSIS_TIMEOUT_SECONDS / FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS
  parse, default, and fall back safely.
"""

import asyncio

import pytest

from app.agents.fundamental_agent import FundamentalAgent
from app.agents.technical_agent import TechnicalAgent
from app.config import (
    DEFAULT_ANALYSIS_TIMEOUT_SECONDS,
    DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS,
    analysis_timeout_seconds,
    fundamental_refresh_timeout_seconds,
)
from tests.test_technical_agent import create_candles

_VALID_TECHNICAL = """
{
    "direction": "BUY",
    "confidence": 0.7,
    "summary": "Recovered.",
    "reasoning": ["trend up"]
}
"""

_VALID_FUNDAMENTAL = """
{
    "direction": "HOLD",
    "confidence": 0.5,
    "summary": "Mixed.",
    "reasoning": ["mixed data"]
}
"""


class _ScriptedLLM:
    """LLM fake honouring a script of responses."""

    def __init__(self, script: list[str]):
        self._script = list(script)
        self.calls = 0

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        self.calls += 1
        return self._script[min(self.calls - 1, len(self._script) - 1)]


class _EmptyRAG:
    async def retrieve(self, symbol, limit=16):
        return []


@pytest.mark.asyncio
async def test_technical_agent_recovers_from_transient_bad_json():
    agent = TechnicalAgent(
        llm_provider=_ScriptedLLM(["not json", _VALID_TECHNICAL])
    )

    result = await agent.run(
        {
            "symbol": "EURUSD",
            "timeframe": "OneHour",
            "market_data": create_candles(),
        }
    )

    assert result["technical_analysis"]["direction"] == "BUY"


@pytest.mark.asyncio
async def test_technical_agent_still_fails_on_persistent_bad_json():
    agent = TechnicalAgent(
        llm_provider=_ScriptedLLM(["garbage", "also garbage"])
    )

    with pytest.raises(ValueError):
        await agent.run(
            {
                "symbol": "EURUSD",
                "timeframe": "OneHour",
                "market_data": create_candles(),
            }
        )


@pytest.mark.asyncio
async def test_fundamental_agent_recovers_from_transient_bad_json():
    agent = FundamentalAgent(
        llm_provider=_ScriptedLLM(["{oops", _VALID_FUNDAMENTAL]),
        rag_service=_EmptyRAG(),
    )

    result = await agent.run(
        {"symbol": "EURUSD", "timeframe": "OneHour"}
    )

    assert result["fundamental_analysis"]["direction"] == "HOLD"


def test_intraday_prompt_carries_recency_note():
    prompt = FundamentalAgent._build_prompt(
        symbol="EURUSD", timeframe="FifteenMinutes", evidence=[]
    )

    assert "intraday" in prompt.lower()
    assert "HOLD" in prompt


def test_swing_prompt_has_no_recency_note():
    prompt = FundamentalAgent._build_prompt(
        symbol="EURUSD", timeframe="OneDay", evidence=[]
    )

    assert "intraday" not in prompt.lower()


def test_mt5_factory_rejects_non_numeric_login(monkeypatch):
    from app.services import market_data_provider_factory as factory

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setenv("MT5_LOGIN", "abc")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "srv")

    with pytest.raises(RuntimeError, match="MT5_LOGIN"):
        factory.create_market_data_provider()


def test_mt5_factory_rejects_bad_timeout(monkeypatch):
    from app.services import market_data_provider_factory as factory

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setenv("MT5_LOGIN", "123")
    monkeypatch.setenv("MT5_PASSWORD", "pw")
    monkeypatch.setenv("MT5_SERVER", "srv")
    monkeypatch.setenv("MT5_TIMEOUT_SECONDS", "nope")

    with pytest.raises(RuntimeError, match="MT5_TIMEOUT_SECONDS"):
        factory.create_market_data_provider()


def test_timeout_helpers_default_and_reject_garbage(monkeypatch):
    analysis_timeout_seconds.cache_clear()
    fundamental_refresh_timeout_seconds.cache_clear()
    monkeypatch.delenv("ANALYSIS_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv(
        "FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS", raising=False
    )

    try:
        assert analysis_timeout_seconds() == (
            DEFAULT_ANALYSIS_TIMEOUT_SECONDS
        )
        assert fundamental_refresh_timeout_seconds() == (
            DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS
        )

        monkeypatch.setenv("ANALYSIS_TIMEOUT_SECONDS", "bad")
        monkeypatch.setenv(
            "FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS", "-5"
        )
        analysis_timeout_seconds.cache_clear()
        fundamental_refresh_timeout_seconds.cache_clear()

        assert analysis_timeout_seconds() == (
            DEFAULT_ANALYSIS_TIMEOUT_SECONDS
        )
        assert fundamental_refresh_timeout_seconds() == (
            DEFAULT_FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS
        )
    finally:
        analysis_timeout_seconds.cache_clear()
        fundamental_refresh_timeout_seconds.cache_clear()


@pytest.mark.asyncio
async def test_slow_fundamental_source_degrades_to_cache(monkeypatch):
    """One hung source must not stall the whole refresh (C-06)."""

    from app.fundamentals.service import FundamentalRAGService

    monkeypatch.setenv(
        "FUNDAMENTAL_REFRESH_TIMEOUT_SECONDS", "0.05"
    )
    fundamental_refresh_timeout_seconds.cache_clear()

    service = FundamentalRAGService.__new__(FundamentalRAGService)

    async def _hang(*args, **kwargs):
        await asyncio.sleep(10)

    async def _fast(*args, **kwargs):
        return None

    service._refresh_world_bank = _hang
    service._refresh_sotw = _fast
    service._refresh_business_quant = _fast

    class _Store:
        def retrieve(self, currencies, query, limit):
            return [{"cached": True}]

    service.store = _Store()

    try:
        docs = await service.retrieve("EURUSD", limit=4)
        assert docs == [{"cached": True}]
    finally:
        fundamental_refresh_timeout_seconds.cache_clear()

"""Phase 1 (SQA Must-Fix) regression tests.

Each test pins one audit finding so it cannot regress silently:

* C-01 — production without AI_SERVICE_API_KEY fails closed (503), never
  serves quota-burning endpoints open; local dev stays frictionless.
* C-01b — a bare CORS "*" is rejected (must list origins explicitly).
* C-02 — the 0.50 threshold claim is net of spread+slippage; frictionless
  runs stay valid but must say so via total_cost == 0.
* C-03 — stale feeds and gapped feeds fail closed (503-class RuntimeError,
  never cached); the graph drops the still-forming bar.
* C-04 — OpenAI retries transient failures but fails fast on permanent
  ones (401 bad key = single attempt).
* C-07 — concurrent misses for the same key trigger one provider fetch
  (single-flight), not N.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.agents.market_data_agent import drop_forming_candle
from app.backtesting.engine import BacktestEngine
from app.config import cors_origins, expected_api_key, is_production
from app.llm.llm_errors import LLMUnavailableError
from app.llm.openai_provider import OpenAIProvider
from app.main import app
from app.schemas.market import Candle, MarketData
from app.services.market_data_cache import (
    MarketDataCache,
    detect_candle_gap_seconds,
    max_candle_age_seconds,
)
from app.services.market_data_provider import MarketDataProvider
from app.services.market_data_service import MarketDataService
from tests.test_backtesting import _frame, _quiet_rows, _signal_row


@pytest.fixture
def _clean_auth_caches():
    expected_api_key.cache_clear()
    is_production.cache_clear()
    yield
    expected_api_key.cache_clear()
    is_production.cache_clear()


def test_production_without_api_key_fails_closed(
    monkeypatch, _clean_auth_caches
):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("AI_SERVICE_API_KEY", raising=False)
    expected_api_key.cache_clear()
    is_production.cache_clear()

    assert is_production() is True

    with TestClient(app) as client:
        response = client.get(
            "/market-data/EURUSD",
            params={"timeframe": "FifteenMinutes"},
        )

    assert response.status_code == 503
    assert "AI_SERVICE_API_KEY" in response.json()["detail"]


def test_production_with_api_key_enforces_guard(
    monkeypatch, _clean_auth_caches
):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("AI_SERVICE_API_KEY", "prod-secret")
    expected_api_key.cache_clear()
    is_production.cache_clear()

    with TestClient(app) as client:
        response = client.get(
            "/market-data/EURUSD",
            params={"timeframe": "FifteenMinutes"},
        )

    assert response.status_code == 401


def test_cors_wildcard_is_rejected(monkeypatch):
    cors_origins.cache_clear()
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "*, http://a")

    try:
        assert cors_origins() == ["http://a"]
    finally:
        cors_origins.cache_clear()


def test_costed_backtest_net_is_below_gross():
    rows = [_signal_row(0)]
    rows.extend(_quiet_rows(3))
    frame = _frame(rows)

    engine = BacktestEngine(
        max_holding_period=2,
        spread=0.00015,
        slippage=0.00005,
    )
    trades = engine.run(frame, probability_threshold=0.6)

    assert len(trades) == 1
    assert trades[0].cost == pytest.approx(0.00025)
    assert trades[0].profit == pytest.approx(-0.00025)


def _candles(n: int, start: datetime, step_seconds: int) -> list[Candle]:
    return [
        Candle(
            timestamp=start + timedelta(seconds=i * step_seconds),
            open=1.1,
            high=1.2,
            low=1.0,
            close=1.15,
            volume=1.0,
        )
        for i in range(n)
    ]


def test_stale_feed_fails_closed():
    stale = MarketData(
        symbol="EURUSD",
        timeframe="OneMinute",
        candles=_candles(
            3,
            datetime.now(timezone.utc) - timedelta(hours=1),
            60,
        ),
    )

    class _StaleProvider(MarketDataProvider):
        async def get_market_data(
            self, symbol: str, timeframe: str, limit: int = 100
        ):
            return stale

    service = MarketDataService(
        provider=_StaleProvider(),
        cache=MarketDataCache(),
    )

    with pytest.raises(RuntimeError, match="stale"):
        asyncio.run(
            service.get_market_data(
                symbol="EURUSD",
                timeframe="OneMinute",
            )
        )


def test_gapped_feed_fails_closed():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    first = _candles(1, now - timedelta(minutes=10), 60)
    second = Candle(
        timestamp=now,
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=1.0,
    )
    gapped = MarketData(
        symbol="EURUSD",
        timeframe="OneMinute",
        candles=first + [second],
    )

    assert detect_candle_gap_seconds(
        gapped.candles, "OneMinute"
    ) == pytest.approx(600.0)

    class _GappedProvider(MarketDataProvider):
        async def get_market_data(
            self, symbol: str, timeframe: str, limit: int = 100
        ):
            return gapped

    service = MarketDataService(
        provider=_GappedProvider(),
        cache=MarketDataCache(),
    )

    with pytest.raises(RuntimeError, match="gap"):
        asyncio.run(
            service.get_market_data(
                symbol="EURUSD",
                timeframe="OneMinute",
            )
        )


def test_max_candle_age_budget_is_two_bars_plus_delay():
    assert max_candle_age_seconds("OneMinute") == 180
    assert max_candle_age_seconds("FifteenMinutes") == 1860


def test_forming_candle_is_dropped_for_fifteen_minutes():
    now = datetime.now(timezone.utc)
    boundary = datetime.fromtimestamp(
        int(now.timestamp()) // 900 * 900, tz=timezone.utc
    )
    closed_ts = (boundary - timedelta(minutes=15)).isoformat()
    forming_ts = (boundary + timedelta(minutes=1)).isoformat()

    candles = [
        {"timestamp": closed_ts, "close": 1.1},
        {"timestamp": forming_ts, "close": 1.2},
    ]

    kept = drop_forming_candle(candles, "FifteenMinutes")

    assert len(kept) == 1
    assert kept[0]["close"] == 1.1


class _StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class _ScriptedClient:
    def __init__(self, script: list):
        self._script = list(script)
        self.calls = 0
        self.responses = self

    async def create(self, **kwargs):
        self.calls += 1
        action = self._script[min(self.calls - 1, len(self._script) - 1)]

        if isinstance(action, Exception):
            raise action

        class _Response:
            output_text = action

        return _Response()


@pytest.mark.asyncio
async def test_openai_401_fails_fast_without_retry(monkeypatch):
    monkeypatch.setenv("OPENAI_RETRY_BASE_SECONDS", "0.01")
    monkeypatch.setenv("OPENAI_RETRY_MAX_SECONDS", "0.02")
    monkeypatch.setenv("OPENAI_REQUEST_DEADLINE_SECONDS", "5")

    client = _ScriptedClient([_StatusError(401)])
    provider = OpenAIProvider(api_key="bad", model="m", client=client)

    with pytest.raises(LLMUnavailableError):
        await provider.generate(system_prompt="s", user_prompt="u")

    assert client.calls == 1


@pytest.mark.asyncio
async def test_openai_429_then_success_retries(monkeypatch):
    monkeypatch.setenv("OPENAI_RETRY_BASE_SECONDS", "0.01")
    monkeypatch.setenv("OPENAI_RETRY_MAX_SECONDS", "0.02")
    monkeypatch.setenv("OPENAI_REQUEST_DEADLINE_SECONDS", "5")

    client = _ScriptedClient([_StatusError(429), "hello"])
    provider = OpenAIProvider(api_key="k", model="m", client=client)

    assert await provider.generate(
        system_prompt="s", user_prompt="u"
    ) == "hello"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_concurrent_misses_trigger_single_provider_fetch():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    fresh = MarketData(
        symbol="EURUSD",
        timeframe="OneMinute",
        candles=_candles(3, now - timedelta(minutes=3), 60),
    )
    calls = {"n": 0}

    class _CountingProvider(MarketDataProvider):
        async def get_market_data(
            self, symbol: str, timeframe: str, limit: int = 100
        ):
            calls["n"] += 1
            await asyncio.sleep(0.05)
            return fresh

    service = MarketDataService(
        provider=_CountingProvider(),
        cache=MarketDataCache(),
    )

    results = await asyncio.gather(
        *(
            service.get_market_data(
                symbol="EURUSD",
                timeframe="OneMinute",
            )
            for _ in range(8)
        )
    )

    assert calls["n"] == 1
    assert all(result is results[0] for result in results)

"""Batch endpoint isolation and webhook push delivery (P2/P4)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api import analysis as analysis_route
from app.config import analysis_batch_limit
from app.config import webhook_allowlist as _allowlist
from app.services import webhook_delivery


class _FakeService:
    async def analyze(self, symbol: str, timeframe: str) -> dict:
        section = {
            "direction": "BUY",
            "confidence": 0.7,
            "summary": f"{symbol} ok",
        }
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "technical_analysis": dict(section),
            "fundamental_analysis": dict(section),
            "quant_prediction": dict(section),
            "risk_assessment": {
                "risk_level": "LOW",
                "approved": True,
                "agreement": 1.0,
                "reason": "agree",
            },
            "final_decision": {
                "direction": "BUY",
                "confidence": 0.7,
                "reasoning": "agree",
            },
        }


@pytest.fixture
def client(monkeypatch):
    from app.main import app

    monkeypatch.setattr(
        analysis_route,
        "get_analysis_service",
        lambda: _FakeService(),
    )
    analysis_batch_limit.cache_clear()
    _allowlist.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    analysis_batch_limit.cache_clear()
    _allowlist.cache_clear()


def _item(symbol: str, timeframe: str = "FifteenMinutes") -> dict:
    return {
        "forex_pair_id": symbol,
        "symbol": symbol,
        "timeframe": timeframe,
    }


def test_batch_returns_results_for_each_item(client):
    response = client.post(
        "/analysis/batch",
        json={"requests": [_item("EURUSD"), _item("GBPUSD", "OneHour")]},
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["results"]) == 2
    assert body["errors"] == []
    assert body["results"][0]["symbol"] == "EURUSD"


def test_batch_captures_per_item_errors(client, monkeypatch):
    class _FlakyService(_FakeService):
        async def analyze(self, symbol: str, timeframe: str) -> dict:
            if symbol == "GBPUSD":
                raise ValueError("LLM returned invalid JSON.")

            return await super().analyze(symbol, timeframe)

    monkeypatch.setattr(
        analysis_route,
        "get_analysis_service",
        lambda: _FlakyService(),
    )

    response = client.post(
        "/analysis/batch",
        json={"requests": [_item("EURUSD"), _item("GBPUSD")]},
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["results"]) == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["index"] == 1
    assert body["errors"][0]["status"] == 502


def test_batch_captures_market_data_outage_per_item(client, monkeypatch):
    class _OutageService(_FakeService):
        async def analyze(self, symbol: str, timeframe: str) -> dict:
            raise RuntimeError("Twelve Data error: out of credits.")

    monkeypatch.setattr(
        analysis_route,
        "get_analysis_service",
        lambda: _OutageService(),
    )

    response = client.post(
        "/analysis/batch",
        json={"requests": [_item("EURUSD")]},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["results"] == []
    assert body["errors"][0]["status"] == 503


def test_batch_enforces_limit(client, monkeypatch):
    monkeypatch.setenv("ANALYSIS_BATCH_LIMIT", "1")
    analysis_batch_limit.cache_clear()

    response = client.post(
        "/analysis/batch",
        json={"requests": [_item("EURUSD"), _item("GBPUSD")]},
    )

    assert response.status_code == 422


def test_batch_delivers_webhook_when_requested(client, monkeypatch):
    delivered: list = []

    async def _fake_deliver(url: str, payload: dict) -> bool:
        delivered.append((url, payload))
        return True

    monkeypatch.setattr(
        analysis_route,
        "deliver_webhook",
        _fake_deliver,
    )

    response = client.post(
        "/analysis/batch",
        json={
            "requests": [_item("EURUSD")],
            "webhook_url": "https://hooks.example.com/signal",
        },
    )

    assert response.status_code == 200
    assert len(delivered) == 1
    assert delivered[0][0] == "https://hooks.example.com/signal"


def test_webhook_allowlist_denies_by_default(monkeypatch):
    monkeypatch.delenv("WEBHOOK_ALLOWLIST", raising=False)
    _allowlist.cache_clear()

    try:
        assert webhook_delivery.webhook_allowed("https://evil.example/x") is False
        assert webhook_delivery.webhook_allowed("http://localhost:9000/x") is True
    finally:
        _allowlist.cache_clear()


def test_webhook_delivery_failure_is_non_fatal(monkeypatch):
    monkeypatch.setenv("WEBHOOK_ALLOWLIST", "hooks.example.com")
    _allowlist.cache_clear()

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("no network")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(webhook_delivery.httpx, "AsyncClient", _BoomClient)

    try:
        delivered = asyncio.run(
            webhook_delivery.deliver_webhook(
                "https://hooks.example.com/signal",
                {"ok": True},
            )
        )
        assert delivered is False
    finally:
        _allowlist.cache_clear()


def test_single_analysis_delivers_webhook_when_requested(
    client,
    monkeypatch,
):
    """POST /analysis pushes too - that is the route the C# gateway calls.

    The hosted signal generator reaches the local MT5 bridge through this
    single-pair endpoint, so without push support here the whole hosted ->
    local trading path would silently stop at the gateway.
    """

    delivered: list = []

    async def _fake_deliver(url: str, payload: dict) -> bool:
        delivered.append((url, payload))
        return True

    monkeypatch.setattr(
        analysis_route,
        "deliver_webhook",
        _fake_deliver,
    )

    response = client.post(
        "/analysis",
        json={
            "forex_pair_id": "EURUSD",
            "symbol": "EURUSD",
            "timeframe": "FifteenMinutes",
            "webhook_url": "https://hooks.example.com/signal",
        },
    )

    assert response.status_code == 200
    assert len(delivered) == 1
    assert delivered[0][0] == "https://hooks.example.com/signal"
    assert delivered[0][1]["symbol"] == "EURUSD"


def test_single_analysis_without_webhook_delivers_nothing(
    client,
    monkeypatch,
):
    delivered: list = []

    async def _fake_deliver(url: str, payload: dict) -> bool:
        delivered.append((url, payload))
        return True

    monkeypatch.setattr(
        analysis_route,
        "deliver_webhook",
        _fake_deliver,
    )

    response = client.post(
        "/analysis",
        json=_item("EURUSD"),
    )

    assert response.status_code == 200
    assert delivered == []


def test_single_analysis_webhook_failure_still_returns_the_signal(
    client,
    monkeypatch,
):
    """A push failure is logged, never raised: the caller keeps its signal.

    The failure is injected at the transport layer, because that is where it
    really happens (tunnel down, receiver asleep, DNS failure) and because
    ``deliver_webhook`` is contracted to absorb exactly that.
    """

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("no network")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setenv("WEBHOOK_ALLOWLIST", "hooks.example.com")
    _allowlist.cache_clear()
    monkeypatch.setattr(
        webhook_delivery.httpx,
        "AsyncClient",
        _BoomClient,
    )

    response = client.post(
        "/analysis",
        json={
            **_item("EURUSD"),
            "webhook_url": "https://hooks.example.com/signal",
        },
    )

    assert response.status_code == 200
    assert response.json()["symbol"] == "EURUSD"


def test_batch_item_webhook_is_ignored(client, monkeypatch):
    """Only the batch-level ``webhook_url`` fires, never an item's.

    An item-level value would multiply deliveries and let a single pair in a
    watchlist post to an arbitrary receiver, so it is parsed but ignored.
    """

    delivered: list = []

    async def _fake_deliver(url: str, payload: dict) -> bool:
        delivered.append((url, payload))
        return True

    monkeypatch.setattr(
        analysis_route,
        "deliver_webhook",
        _fake_deliver,
    )

    response = client.post(
        "/analysis/batch",
        json={
            "requests": [
                {
                    **_item("EURUSD"),
                    "webhook_url": "https://item.example.com/signal",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert delivered == []


def test_batch_concurrency_is_bounded(client, monkeypatch):
    """Phase 2 SQA: at most 3 items run concurrently (T-05).

    A 6-pair batch of slow items must succeed while never exceeding the
    semaphore ceiling — otherwise a full batch bursts 10x LLM + provider +
    RAG calls and trips every quota at once.
    """

    in_flight = 0
    peak = 0

    class _SlowService(_FakeService):
        async def analyze(self, symbol: str, timeframe: str) -> dict:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.05)
                return await super().analyze(symbol, timeframe)
            finally:
                in_flight -= 1

    monkeypatch.setattr(
        analysis_route,
        "get_analysis_service",
        lambda: _SlowService(),
    )

    response = client.post(
        "/analysis/batch",
        json={
            "requests": [
                _item(symbol)
                for symbol in (
                    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP",
                )
            ]
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["results"]) == 6
    assert body["errors"] == []
    assert peak <= 3
    assert peak > 1  # genuinely concurrent, not serialised

from datetime import datetime, timedelta, timezone

import pytest

from app.agents import market_data_agent
from app.graphs.forex_analysis_graph import (
    build_forex_analysis_graph,
)
from app.llm.demo_provider import (
    DemoLLMProvider,
)
from app.schemas.market import Candle, MarketData


class FakeFundamentalRAGService:

    async def retrieve(
        self,
        symbol: str,
        limit: int = 16,
    ) -> list:
        return [
            {
                "source": "TEST",
                "country_code": "USA",
                "currency": "USD",
                "indicator_code": "TEST.RATE",
                "indicator_name": "Test Interest Rate",
                "period": "2026",
                "observation_date": "2026-01-01",
                "value": 4.0,
                "unit": "percent",
                "content": (
                    "Test economic evidence for graph testing."
                ),
            }
        ][:limit]


class FakeMarketDataService:
    """In-memory stand-in so the graph test never touches the network.

    The previous version of this test invoked the real Twelve Data provider
    with the committed API key, which made the suite non-deterministic and
    consumed paid quota on every run.
    """

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> MarketData:

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)

        candles = []

        price = 1.1000

        for i in range(limit):
            price += 0.0005
            stamp = start + timedelta(minutes=15 * i)

            candles.append(
                Candle(
                    timestamp=stamp,
                    open=price,
                    high=price + 0.002,
                    low=price - 0.002,
                    close=price + 0.001,
                    volume=1000.0,
                )
            )

        return MarketData(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )


@pytest.fixture
def fake_market_data(monkeypatch):
    monkeypatch.setattr(
        market_data_agent,
        "get_market_data_service",
        lambda: FakeMarketDataService(),
    )


@pytest.mark.asyncio
async def test_full_forex_analysis_graph(fake_market_data):

    graph = build_forex_analysis_graph(
        DemoLLMProvider(),
        FakeFundamentalRAGService(),
    )

    result = await graph.ainvoke(
        {
            "symbol": "EURUSD",
            "timeframe": "FifteenMinutes",
        }
    )

    assert "technical_analysis" in result
    assert "fundamental_analysis" in result
    assert "quant_prediction" in result
    assert "risk_assessment" in result
    assert "final_decision" in result


@pytest.mark.asyncio
async def test_graph_result_maps_to_response(fake_market_data):
    """A complete graph result must round-trip through the response mapper."""

    from app.services.ai_response_mapper import (
        map_graph_result_to_response,
    )

    graph = build_forex_analysis_graph(
        DemoLLMProvider(),
        FakeFundamentalRAGService(),
    )

    result = await graph.ainvoke(
        {
            "symbol": "EURUSD",
            "timeframe": "FifteenMinutes",
        }
    )

    response = map_graph_result_to_response(result)

    assert response.symbol == "EURUSD"
    assert response.timeframe == "FifteenMinutes"
    assert 0.0 <= response.final_decision.confidence <= 1.0
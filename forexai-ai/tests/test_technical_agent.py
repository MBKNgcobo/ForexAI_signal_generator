import pytest

from app.agents.technical_agent import (
    TechnicalAgent,
)
from app.services.confidence_calibration import calibrate_confidence

from tests.fakes.fake_llm import (
    FakeLLMProvider,
)


def create_candles() -> list[dict]:

    candles = []

    price = 1.1000

    for i in range(60):

        open_price = price
        close_price = price + 0.001

        high_price = (
            close_price + 0.0005
        )

        low_price = (
            open_price - 0.0005
        )

        candles.append(
            {
                "timestamp": str(i),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1000,
            }
        )

        price = close_price

    return candles


@pytest.mark.asyncio
async def test_technical_agent_uses_llm():

    fake_llm = FakeLLMProvider(
        """
        {
            "direction": "BUY",
            "confidence": 0.85,
            "summary": "Bullish technical conditions.",
            "reasoning": [
                "EMA20 is above EMA50.",
                "Momentum is positive."
            ]
        }
        """
    )

    agent = TechnicalAgent(
        llm_provider=fake_llm
    )

    result = await agent.run(
        {
            "symbol": "EURUSD",
            "timeframe": "FourHours",
            "market_data": create_candles(),
        }
    )

    technical = result[
        "technical_analysis"
    ]

    assert technical[
        "direction"
    ] == "BUY"

    # LLM raw 0.85 is calibrated on the technical table; raw kept for audit.
    assert technical[
        "raw_confidence"
    ] == 0.85

    assert technical[
        "confidence"
    ] == calibrate_confidence(0.85, "technical")

    assert technical[
        "summary"
    ] == "Bullish technical conditions."

    assert len(
        technical["reasoning"]
    ) == 2

    assert technical[
        "ema_20"
    ] is not None

    assert technical[
        "ema_50"
    ] is not None

    assert technical[
        "rsi"
    ] is not None

    assert technical[
        "atr"
    ] is not None

@pytest.mark.asyncio
async def test_technical_agent_rejects_invalid_json():

    fake_llm = FakeLLMProvider(
        "This is not JSON."
    )

    agent = TechnicalAgent(
        llm_provider=fake_llm
    )

    with pytest.raises(ValueError):
        await agent.run(
            {
                "symbol": "EURUSD",
                "timeframe": "FourHours",
                "market_data": create_candles(),
            }
        )

@pytest.mark.asyncio
async def test_technical_agent_rejects_invalid_confidence():

    fake_llm = FakeLLMProvider(
        """
        {
            "direction": "BUY",
            "confidence": 2.5,
            "summary": "Invalid confidence.",
            "reasoning": []
        }
        """
    )

    agent = TechnicalAgent(
        llm_provider=fake_llm
    )

    with pytest.raises(Exception):
        await agent.run(
            {
                "symbol": "EURUSD",
                "timeframe": "FourHours",
                "market_data": create_candles(),
            }
        )
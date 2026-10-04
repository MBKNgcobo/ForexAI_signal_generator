"""Fundamental agent parsing and evidence shaping.

The agent turns untrusted LLM JSON and retrieved documents into the
``fundamental_analysis`` section; both must be validated, never assumed.
"""

import pytest

from app.agents.fundamental_agent import FundamentalAgent
from app.services.confidence_calibration import calibrate_confidence

from tests.fakes.fake_llm import FakeLLMProvider

_VALID = """
{
  "direction": "BUY",
  "confidence": 0.6,
  "summary": "Supportive data.",
  "reasoning": ["rate higher", "inflation stable"]
}
"""


class _FakeRAGService:
    def __init__(self, documents):
        self._documents = documents

    async def retrieve(self, symbol, limit=16):
        return self._documents[:limit]


def _agent(response):
    return FundamentalAgent(
        llm_provider=FakeLLMProvider(response),
        rag_service=_FakeRAGService([]),
    )


@pytest.mark.asyncio
async def test_agent_parses_valid_response():
    result = await _agent(_VALID).run(
        {"symbol": "EURUSD", "timeframe": "OneHour"}
    )

    analysis = result["fundamental_analysis"]

    assert analysis["direction"] == "BUY"
    assert analysis["raw_confidence"] == 0.6
    assert analysis["confidence"] == calibrate_confidence(0.6, "fundamental")
    assert len(analysis["reasoning"]) == 2


@pytest.mark.asyncio
async def test_agent_shapes_evidence_from_documents():
    documents = [
        {
            "source": "WORLD_BANK",
            "country_code": "USA",
            "currency": "USD",
            "indicator_code": "FP.CPI.TOTL.ZG",
            "indicator_name": "Inflation",
            "period": "2025",
            "observation_date": "2025-01-01",
            "value": 3.1,
            "unit": "%",
            "content": "US inflation 3.1%",
            "extra": "ignored",
        }
    ]

    agent = FundamentalAgent(
        llm_provider=FakeLLMProvider(_VALID),
        rag_service=_FakeRAGService(documents),
    )

    result = await agent.run({"symbol": "EURUSD", "timeframe": "OneHour"})

    evidence = result["fundamental_analysis"]["evidence"]

    assert evidence[0]["source"] == "WORLD_BANK"
    assert "extra" not in evidence[0]


def test_parse_rejects_non_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        FundamentalAgent._parse_response("not json")


def test_parse_rejects_missing_fields():
    with pytest.raises(ValueError, match="missing"):
        FundamentalAgent._parse_response('{"direction": "BUY"}')


def test_parse_rejects_bad_direction():
    payload = (
        '{"direction": "MAYBE", "confidence": 0.5, "summary": "s", "reasoning": []}'
    )

    with pytest.raises(ValueError, match="unsupported direction"):
        FundamentalAgent._parse_response(payload)


def test_parse_rejects_out_of_range_confidence():
    payload = (
        '{"direction": "BUY", "confidence": 1.5, "summary": "s", "reasoning": []}'
    )

    with pytest.raises(ValueError, match="between 0 and 1"):
        FundamentalAgent._parse_response(payload)

"""Quant agent wiring and its fail-safe behaviour.

The ensemble loads large, git-ignored ``.joblib`` artifacts, so these tests
verify the loading is lazy (an import must not require the artifacts) and that
a model failure degrades to NO_TRADE rather than raising into the graph.
"""

import pytest

from app.agents import quant_agent


def _candles(count: int = 260) -> list[dict]:
    return [
        {
            "datetime": f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00Z",
            "open": 1.1000 + i * 0.0001,
            "high": 1.1010 + i * 0.0001,
            "low": 1.0990 + i * 0.0001,
            "close": 1.1005 + i * 0.0001,
            "volume": 1000.0,
        }
        for i in range(count)
    ]


def test_get_quant_model_is_lazy(monkeypatch):
    """Construction must happen on call, not at import time."""

    def _boom(*args, **kwargs):
        raise FileNotFoundError("no artifact")

    monkeypatch.setattr(quant_agent, "SklearnQuantModel", _boom)
    quant_agent.get_quant_model.cache_clear()

    with pytest.raises(FileNotFoundError):
        quant_agent.get_quant_model()

    quant_agent.get_quant_model.cache_clear()


def test_run_quant_agent_falls_back_to_no_trade(monkeypatch):
    def _boom():
        raise FileNotFoundError("no artifact")

    monkeypatch.setattr(quant_agent, "get_quant_model", _boom)

    result = quant_agent.run_quant_agent(
        {"market_data": _candles()}
    )

    prediction = result["quant_prediction"]

    assert prediction["direction"] == "NO_TRADE"
    assert prediction["confidence"] == 0.0
    assert prediction["model_agreement"] == 0.0

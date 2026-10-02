"""Decision agent gate tests.

The decision agent is the last control before a recommendation reaches the
client: risk rejection must always win and confidence must collapse to zero.
"""

import pytest

from app.agents.decision_agent import run_decision_agent


def _state(
    directions=("BUY", "BUY", "BUY"),
    risk_approved=True,
    confidences=(0.8, 0.7, 0.9),
    risk_level="LOW",
):
    technical, fundamental, quant = directions

    return {
        "technical_analysis": {
            "direction": technical,
            "confidence": confidences[0],
        },
        "fundamental_analysis": {
            "direction": fundamental,
            "confidence": confidences[1],
        },
        "quant_prediction": {
            "direction": quant,
            "confidence": confidences[2],
        },
        "risk_assessment": {
            "approved": risk_approved,
            "risk_level": risk_level,
        },
    }


def test_unanimous_direction_is_carried_through():

    final = run_decision_agent(_state())["final_decision"]

    assert final["direction"] == "BUY"
    assert final["confidence"] == pytest.approx(
        (0.8 + 0.7 + 0.9) / 3,
        abs=1e-4,
    )


def test_risk_rejection_forces_no_trade_and_zero_confidence():

    final = run_decision_agent(
        _state(risk_approved=False, risk_level="HIGH")
    )["final_decision"]

    assert final["direction"] == "NO_TRADE"
    assert final["confidence"] == 0.0
    assert "did not approve" in final["reasoning"]


def test_split_vote_yields_hold():

    final = run_decision_agent(
        _state(directions=("BUY", "SELL", "HOLD"))
    )["final_decision"]

    assert final["direction"] == "HOLD"


def test_two_of_three_buy_majority_is_buy():

    final = run_decision_agent(
        _state(directions=("BUY", "BUY", "SELL"))
    )["final_decision"]

    assert final["direction"] == "BUY"


def test_empty_state_is_safe():

    final = run_decision_agent({})["final_decision"]

    assert final["direction"] == "NO_TRADE"
    assert final["confidence"] == 0.0
    assert final["reasoning"]


def test_sell_majority_becomes_sell_when_approved():

    final = run_decision_agent(
        _state(
            directions=("SELL", "SELL", "SELL"),
            confidences=(0.6, 0.6, 0.6),
        )
    )["final_decision"]

    assert final["direction"] == "SELL"

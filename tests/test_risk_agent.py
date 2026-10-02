"""Risk agent policy tests.

The risk gate is the only thing standing between specialist opinions and an
actionable trade, so it needs direct coverage rather than only being
exercised through the full graph.
"""

import pytest

from app.agents.risk_agent import (
    STOP_LOSS_ATR_MULTIPLIER,
    TAKE_PROFIT_ATR_MULTIPLIER,
    run_risk_agent,
)


def _state(
    technical_direction="BUY",
    fundamental_direction="BUY",
    quant_direction="BUY",
    quant_probability=0.80,
    quant_probabilities=None,
    model_agreement=0.75,
    current_price=1.1000,
    atr=0.0020,
):
    return {
        "technical_analysis": {
            "direction": technical_direction,
            "confidence": 0.8,
            "current_price": current_price,
            "atr": atr,
        },
        "fundamental_analysis": {
            "direction": fundamental_direction,
            "confidence": 0.7,
        },
        "quant_prediction": {
            "direction": quant_direction,
            "confidence": 0.9,
            "probability": quant_probability,
            "model_agreement": model_agreement,
            "probabilities": quant_probabilities or {},
        },
    }


def test_unanimous_direction_is_approved():

    assessment = run_risk_agent(_state())["risk_assessment"]

    assert assessment["approved"] is True
    assert assessment["risk_level"] == "LOW"
    assert assessment["agreement"] == 1.0


def test_minority_direction_is_not_approved():

    # One BUY, one SELL and one HOLD leaves no directional majority.
    assessment = run_risk_agent(
        _state(
            technical_direction="BUY",
            fundamental_direction="SELL",
            quant_direction="HOLD",
        )
    )["risk_assessment"]

    assert assessment["approved"] is False
    assert assessment["risk_level"] == "HIGH"
    assert assessment["entry_price"] is None


def test_two_against_one_majority_is_approved():

    assessment = run_risk_agent(
        _state(
            technical_direction="SELL",
            fundamental_direction="SELL",
            quant_direction="BUY",
        )
    )["risk_assessment"]

    assert assessment["approved"] is True
    assert assessment["entry_price"] is not None


def test_strong_opposing_quant_signal_vetoes_majority():

    # The policy vetoes when the quant agent's stated direction opposes the
    # specialist majority while the model still assigns that majority
    # direction a strong probability.
    assessment = run_risk_agent(
        _state(
            quant_direction="SELL",
            quant_probability=0.75,
            quant_probabilities={"BUY": 0.75, "SELL": 0.15},
        )
    )["risk_assessment"]

    assert assessment["approved"] is False
    assert assessment["risk_level"] == "HIGH"


def test_weak_opposing_quant_signal_does_not_veto():

    assessment = run_risk_agent(
        _state(
            quant_direction="SELL",
            quant_probability=0.30,
            quant_probabilities={"BUY": 0.30, "SELL": 0.65},
        )
    )["risk_assessment"]

    assert assessment["approved"] is True
    assert assessment["risk_level"] == "MEDIUM"


def test_quant_holding_does_not_block_majority():

    assessment = run_risk_agent(
        _state(
            quant_direction="HOLD",
            quant_probability=0.40,
            quant_probabilities={"HOLD": 0.40},
        )
    )["risk_assessment"]

    assert assessment["approved"] is True


def test_trade_parameters_follow_atr_multipliers_for_buy():

    assessment = run_risk_agent(
        _state(current_price=1.1000, atr=0.0020)
    )["risk_assessment"]

    assert assessment["entry_price"] == 1.1000

    assert assessment["stop_loss"] == pytest.approx(
        1.1000 - (0.0020 * STOP_LOSS_ATR_MULTIPLIER)
    )

    assert assessment["take_profit"] == pytest.approx(
        1.1000 + (0.0020 * TAKE_PROFIT_ATR_MULTIPLIER)
    )

    assert assessment["risk_reward"] == pytest.approx(
        TAKE_PROFIT_ATR_MULTIPLIER / STOP_LOSS_ATR_MULTIPLIER
    )


def test_trade_parameters_invert_for_sell():

    assessment = run_risk_agent(
        _state(
            technical_direction="SELL",
            fundamental_direction="SELL",
            quant_direction="SELL",
            current_price=1.1000,
            atr=0.0020,
        )
    )["risk_assessment"]

    assert assessment["stop_loss"] > assessment["entry_price"]
    assert assessment["take_profit"] < assessment["entry_price"]


def test_missing_market_data_leaves_parameters_unset():

    assessment = run_risk_agent(
        _state(current_price=0.0, atr=0.0)
    )["risk_assessment"]

    assert assessment["approved"] is True
    assert assessment["entry_price"] is None
    assert assessment["stop_loss"] is None


def test_garbage_numeric_inputs_do_not_raise():

    state = _state()

    state["technical_analysis"]["current_price"] = "n/a"
    state["technical_analysis"]["atr"] = None

    assessment = run_risk_agent(state)["risk_assessment"]

    assert assessment["entry_price"] is None

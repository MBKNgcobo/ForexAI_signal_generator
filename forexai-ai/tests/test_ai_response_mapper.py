import pytest

from app.services.ai_response_mapper import (
    AnalysisIncompleteError,
    map_graph_result_to_response,
)


def test_mapper_preserves_risk_trade_parameters():

    result = {
        "symbol": "EURUSD",
        "timeframe": "FourHours",

        "technical_analysis": {
            "direction": "BUY",
            "confidence": 0.80,
            "summary": "Bullish technical conditions.",
        },

        "fundamental_analysis": {
            "direction": "BUY",
            "confidence": 0.65,
            "summary": "Moderately bullish.",
        },

        "quant_prediction": {
            "direction": "BUY",
            "confidence": 0.75,
            "summary": "Upward quantitative prediction.",
        },

        "risk_assessment": {
            "risk_level": "LOW",
            "approved": True,
            "agreement": 1.0,
            "reason": "Agents agree.",

            "entry_price": 1.1650,
            "stop_loss": 1.1600,
            "take_profit": 1.1750,
            "risk_reward": 2.0,
        },

        "final_decision": {
            "direction": "BUY",
            "confidence": 0.73,
            "reasoning": "Strong agreement.",
        },
    }

    response = map_graph_result_to_response(
        result
    )

    assert (
        response.risk_assessment.entry_price
        == 1.1650
    )

    assert (
        response.risk_assessment.stop_loss
        == 1.1600
    )

    assert (
        response.risk_assessment.take_profit
        == 1.1750
    )

    assert (
        response.risk_assessment.risk_reward
        == 2.0
    )


def _complete_result() -> dict:
    return {
        "symbol": "EURUSD",
        "timeframe": "OneHour",

        "technical_analysis": {
            "direction": "BUY",
            "confidence": 0.8,
            "summary": "technical",
        },
        "fundamental_analysis": {
            "direction": "BUY",
            "confidence": 0.7,
            "summary": "fundamental",
        },
        "quant_prediction": {
            "direction": "BUY",
            "confidence": 0.9,
            "summary": "quant",
        },
        "risk_assessment": {
            "risk_level": "LOW",
            "approved": True,
            "agreement": 1.0,
            "reason": "agreement",
        },
        "final_decision": {
            "direction": "BUY",
            "confidence": 0.8,
            "reasoning": "reasoning",
        },
    }


@pytest.mark.parametrize(
    "missing_key",
    [
        "technical_analysis",
        "fundamental_analysis",
        "quant_prediction",
        "risk_assessment",
        "final_decision",
        "symbol",
    ],
)
def test_mapper_reports_missing_sections(missing_key):
    """A partial graph result must not escape as an opaque KeyError/500."""

    result = _complete_result()

    result.pop(missing_key)

    with pytest.raises(AnalysisIncompleteError) as excinfo:
        map_graph_result_to_response(result)

    assert missing_key in str(excinfo.value)


def test_mapper_rejects_wrongly_typed_sections():

    result = _complete_result()

    result["risk_assessment"] = "not-a-mapping"

    with pytest.raises(AnalysisIncompleteError):
        map_graph_result_to_response(result)


def test_mapper_allows_optional_trade_parameters_to_be_absent():

    result = _complete_result()

    response = map_graph_result_to_response(result)

    assert response.risk_assessment.entry_price is None
    assert response.risk_assessment.stop_loss is None
    assert response.risk_assessment.take_profit is None
    assert response.risk_assessment.risk_reward is None


def test_mapper_builds_explanation_for_unanimous_signal():

    response = map_graph_result_to_response(_complete_result())

    assert response.explanation is not None
    assert response.explanation.agreement == 1.0
    assert response.explanation.quant_vetoed is False
    assert len(response.explanation.drivers) == 2
    assert response.explanation.dissent == []


def test_mapper_builds_explanation_for_split_signal():

    result = _complete_result()
    result["fundamental_analysis"]["direction"] = "SELL"
    result["final_decision"]["direction"] = "BUY"
    result["risk_assessment"]["agreement"] = 0.67

    response = map_graph_result_to_response(result)

    assert response.explanation is not None
    assert response.explanation.agreement == 0.67
    assert any("fundamental says SELL" in item for item in response.explanation.dissent)


def test_mapper_flags_quant_veto_in_explanation():

    result = _complete_result()
    result["quant_prediction"]["direction"] = "SELL"
    result["quant_prediction"]["probability"] = 0.75
    result["risk_assessment"]["quant_probability"] = 0.75
    result["final_decision"]["direction"] = "NO_TRADE"

    response = map_graph_result_to_response(result)

    assert response.explanation is not None
    assert response.explanation.quant_vetoed is True


def test_mapper_preserves_raw_confidences_when_present():

    result = _complete_result()
    result["technical_analysis"]["raw_confidence"] = 0.85
    result["quant_prediction"]["raw_confidence"] = 0.9

    response = map_graph_result_to_response(result)

    assert response.technical_analysis.raw_confidence == 0.85
    assert response.quant_prediction.raw_confidence == 0.9
    # Absent raw values stay optional, never break older graph states.
    assert response.fundamental_analysis.raw_confidence is None
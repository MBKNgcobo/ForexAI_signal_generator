from app.schemas.ai_response import (
    AgentAnalysis,
    AiAnalysisResponse,
    FinalDecision,
    RiskAssessment,
)

# Fields every graph node must have produced before a response can be built.
_REQUIRED_KEYS = (
    "symbol",
    "timeframe",
    "technical_analysis",
    "fundamental_analysis",
    "quant_prediction",
    "risk_assessment",
    "final_decision",
)


class AnalysisIncompleteError(RuntimeError):
    """The graph returned a partial result and the response cannot be built."""


def _section(result: dict, key: str) -> dict:
    value = result.get(key)

    if value is None:
        raise AnalysisIncompleteError(
            f"Analysis graph result is missing '{key}'."
        )

    if not isinstance(value, dict):
        raise AnalysisIncompleteError(
            f"Analysis graph result '{key}' is not a mapping."
        )

    return value


# This is a boundary pattern.
def map_graph_result_to_response(
    result: dict,
) -> AiAnalysisResponse:
    """Convert a graph result into the public response schema.

    Missing sections previously raised a bare ``KeyError``, which FastAPI
    turned into an opaque 500. Raising ``AnalysisIncompleteError`` lets the
    API layer answer with a precise 502 instead.
    """

    missing = [
        key
        for key in _REQUIRED_KEYS
        if result.get(key) is None
    ]

    if missing:
        raise AnalysisIncompleteError(
            "Analysis graph result is missing: " + ", ".join(missing)
        )

    technical_analysis = _section(result, "technical_analysis")
    fundamental_analysis = _section(result, "fundamental_analysis")
    quant_prediction = _section(result, "quant_prediction")
    risk_assessment = _section(result, "risk_assessment")
    final_decision = _section(result, "final_decision")

    return AiAnalysisResponse(
        symbol=result["symbol"],
        timeframe=result["timeframe"],

        technical_analysis=AgentAnalysis(
            direction=technical_analysis["direction"],
            confidence=technical_analysis["confidence"],
            summary=technical_analysis["summary"],
        ),

        fundamental_analysis=AgentAnalysis(
            direction=fundamental_analysis["direction"],
            confidence=fundamental_analysis["confidence"],
            summary=fundamental_analysis["summary"],
        ),

        quant_prediction=AgentAnalysis(
            direction=quant_prediction["direction"],
            confidence=quant_prediction["confidence"],
            summary=quant_prediction["summary"],
        ),

        risk_assessment=RiskAssessment(
            risk_level=risk_assessment["risk_level"],
            approved=risk_assessment["approved"],
            agreement=risk_assessment["agreement"],
            reason=risk_assessment["reason"],
            entry_price=risk_assessment.get("entry_price"),
            stop_loss=risk_assessment.get("stop_loss"),
            take_profit=risk_assessment.get("take_profit"),
            risk_reward=risk_assessment.get("risk_reward"),
        ),

        final_decision=FinalDecision(
            direction=final_decision["direction"],
            confidence=final_decision["confidence"],
            reasoning=final_decision["reasoning"],
        ),
    )
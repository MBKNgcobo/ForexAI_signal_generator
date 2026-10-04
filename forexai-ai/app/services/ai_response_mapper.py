from app.schemas.ai_response import (
    AgentAnalysis,
    AiAnalysisResponse,
    Explanation,
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


def _safe_confidence(value) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0

    return min(1.0, max(0.0, parsed))


def _build_explanation(
    technical_analysis: dict,
    fundamental_analysis: dict,
    quant_prediction: dict,
    risk_assessment: dict,
    final_decision: dict,
) -> Explanation:
    """Build the auditable "why" from sections the graph already produces.

    No new inference: agreement math, veto flags and per-agent summaries
    are reused. ``drivers`` lists agreeing specialists strongest-first;
    ``dissent`` captures the opposer (if any) with a reason fragment.
    """

    agreement = _safe_confidence(risk_assessment.get("agreement", 0.0))

    quant_agreement = _safe_confidence(
        risk_assessment.get(
            "quant_model_agreement",
            quant_prediction.get("model_agreement", 0.0),
        )
    )

    final_direction = final_decision.get("direction")

    specialists = (
        ("technical", technical_analysis),
        ("fundamental", fundamental_analysis),
        ("quant", quant_prediction),
    )

    drivers: list[str] = []
    dissent: list[str] = []

    for name, section in sorted(
        specialists,
        key=lambda item: _safe_confidence(item[1].get("confidence", 0.0)),
        reverse=True,
    ):
        direction = section.get("direction")
        confidence = _safe_confidence(section.get("confidence", 0.0))

        if direction == final_direction and final_direction in {
            "BUY",
            "SELL",
        }:
            drivers.append(f"{name} agrees ({direction} {confidence:.0%})")
        elif direction in {"BUY", "SELL"} and final_direction in {
            "BUY",
            "SELL",
            "HOLD",
            "NO_TRADE",
        }:
            summary = str(section.get("summary", "")).strip()

            fragment = f": {summary[:120]}" if summary else ""
            dissent.append(f"{name} says {direction}{fragment}")

    quant_direction = quant_prediction.get("direction")
    quant_probability = _safe_confidence(
        risk_assessment.get(
            "quant_probability",
            quant_prediction.get("probability", 0.0),
        )
    )

    quant_vetoed = bool(
        final_direction == "NO_TRADE"
        and quant_direction in {"BUY", "SELL"}
        and quant_probability >= 0.60
    )

    return Explanation(
        agreement=agreement,
        quant_agreement=quant_agreement,
        quant_vetoed=quant_vetoed,
        drivers=drivers[:2],
        dissent=dissent[:2],
    )


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
            raw_confidence=technical_analysis.get("raw_confidence"),
            summary=technical_analysis["summary"],
        ),

        fundamental_analysis=AgentAnalysis(
            direction=fundamental_analysis["direction"],
            confidence=fundamental_analysis["confidence"],
            raw_confidence=fundamental_analysis.get("raw_confidence"),
            summary=fundamental_analysis["summary"],
        ),

        quant_prediction=AgentAnalysis(
            direction=quant_prediction["direction"],
            confidence=quant_prediction["confidence"],
            raw_confidence=quant_prediction.get("raw_confidence"),
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

        explanation=_build_explanation(
            technical_analysis,
            fundamental_analysis,
            quant_prediction,
            risk_assessment,
            final_decision,
        ),
    )
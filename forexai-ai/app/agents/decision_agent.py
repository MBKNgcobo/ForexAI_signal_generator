def run_decision_agent(
    state: dict,
) -> dict:

    # --------------------------------------------------------------
    # Read specialist outputs.
    # --------------------------------------------------------------

    technical = state.get(
        "technical_analysis",
        {},
    )

    fundamental = state.get(
        "fundamental_analysis",
        {},
    )

    quant = state.get(
        "quant_prediction",
        {},
    )

    risk = state.get(
        "risk_assessment",
        {},
    )

    # --------------------------------------------------------------
    # Extract specialist directions.
    # --------------------------------------------------------------

    technical_direction = (
        technical.get("direction")
    )

    fundamental_direction = (
        fundamental.get("direction")
    )

    quant_direction = (
        quant.get("direction")
    )

    opinions = [
        technical_direction,
        fundamental_direction,
        quant_direction,
    ]

    # --------------------------------------------------------------
    # Count directional votes.
    # --------------------------------------------------------------

    buy_count = opinions.count(
        "BUY"
    )

    sell_count = opinions.count(
        "SELL"
    )

    # --------------------------------------------------------------
    # Determine the dominant direction.
    # --------------------------------------------------------------

    if buy_count > sell_count:

        dominant_direction = "BUY"

    elif sell_count > buy_count:

        dominant_direction = "SELL"

    else:

        dominant_direction = "HOLD"

    # --------------------------------------------------------------
    # Risk approval is the final gate.
    #
    # Even if the agents have a majority direction,
    # a failed risk assessment must result in NO_TRADE.
    # --------------------------------------------------------------

    risk_approved = bool(
        risk.get(
            "approved",
            False,
        )
    )

    if not risk_approved:

        final_direction = "NO_TRADE"

    elif dominant_direction in {
        "BUY",
        "SELL",
    }:

        final_direction = (
            dominant_direction
        )

    else:

        final_direction = "HOLD"

    # --------------------------------------------------------------
    # Extract confidence values.
    #
    # These are the values already exposed by the
    # existing Python -> C# response contract.
    # --------------------------------------------------------------

    technical_confidence = float(
        technical.get(
            "confidence",
            0.0,
        )
    )

    fundamental_confidence = float(
        fundamental.get(
            "confidence",
            0.0,
        )
    )

    quant_confidence = float(
        quant.get(
            "confidence",
            0.0,
        )
    )

    confidences = [
        technical_confidence,
        fundamental_confidence,
        quant_confidence,
    ]

    average_confidence = (
        sum(confidences)
        / len(confidences)
        if confidences
        else 0.0
    )

    # --------------------------------------------------------------
    # If risk rejects the trade, don't expose the
    # specialist confidence as the final trade confidence.
    #
    # The system's final actionable decision is NO_TRADE.
    # --------------------------------------------------------------

    if final_direction == "NO_TRADE":

        final_confidence = 0.0

    else:

        final_confidence = (
            average_confidence
        )

    # --------------------------------------------------------------
    # Build a transparent explanation.
    # --------------------------------------------------------------

    reasoning_parts = [
        "Final decision was based on "
        "technical, fundamental, quant, "
        "and risk assessments.",
    ]

    reasoning_parts.append(
        f"Technical direction: "
        f"{technical_direction}."
    )

    reasoning_parts.append(
        f"Fundamental direction: "
        f"{fundamental_direction}."
    )

    reasoning_parts.append(
        f"Quant direction: "
        f"{quant_direction}."
    )

    reasoning_parts.append(
        f"BUY votes: {buy_count}."
    )

    reasoning_parts.append(
        f"SELL votes: {sell_count}."
    )

    reasoning_parts.append(
        f"Risk approved: "
        f"{risk_approved}."
    )

    reasoning_parts.append(
        f"Risk level: "
        f"{risk.get('risk_level', 'UNKNOWN')}."
    )

    # --------------------------------------------------------------
    # Add Quant-specific information when available.
    # --------------------------------------------------------------

    quant_probability = quant.get(
        "probability"
    )

    if quant_probability is not None:

        reasoning_parts.append(
            f"Quant probability: "
            f"{float(quant_probability):.2%}."
        )

    quant_model_agreement = quant.get(
        "model_agreement"
    )

    if quant_model_agreement is not None:

        reasoning_parts.append(
            f"Quant model agreement: "
            f"{float(quant_model_agreement):.2%}."
        )

    # --------------------------------------------------------------
    # Explain a rejected risk assessment.
    # --------------------------------------------------------------

    if not risk_approved:

        reasoning_parts.append(
            "The Risk Agent did not approve "
            "the setup, so the final decision "
            "is NO_TRADE."
        )

    elif final_direction == "HOLD":

        reasoning_parts.append(
            "The specialist directions did "
            "not produce a BUY or SELL majority."
        )

    else:

        reasoning_parts.append(
            f"The final directional decision "
            f"is {final_direction}."
        )

    # --------------------------------------------------------------
    # Return graph state update.
    #
    # This structure remains compatible with
    # the existing ai_response_mapper.py.
    # --------------------------------------------------------------

    return {
        "final_decision": {
            "direction": final_direction,

            "confidence": round(
                final_confidence,
                4,
            ),

            "reasoning": " ".join(
                reasoning_parts
            ),
        }
    }
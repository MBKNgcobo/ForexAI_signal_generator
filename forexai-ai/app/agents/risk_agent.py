from __future__ import annotations

from typing import Any

from app.config import quant_threshold


# ------------------------------------------------------------------
# Trading parameters
#
# These match the parameters used by our first backtest:
#
# Stop Loss  = 1.0 ATR
# Take Profit = 1.5 ATR
#
# This keeps the live signal generation consistent with the
# strategy that we evaluated historically.
# ------------------------------------------------------------------

STOP_LOSS_ATR_MULTIPLIER = 1.0
TAKE_PROFIT_ATR_MULTIPLIER = 1.5


# ------------------------------------------------------------------
# Quant model policy
#
# ``STRONG_QUANT_PROBABILITY`` is the bar for LOW risk and for the
# opposing-quant veto. Validation (113 days, EURUSD 15m) showed 0.60 admits
# ~0.7 engine candidates/day and a negative net, while 0.50 admits ~5.9/day
# with the only profitable net (+0.0471, PF 1.31). Tunable via
# ``QUANT_PROBABILITY_THRESHOLD`` (default 0.50); see ``quant_threshold()``
# in app/config.py. Gate majority logic is unchanged.
# ------------------------------------------------------------------

MIN_QUANT_PROBABILITY = 0.50
STRONG_QUANT_PROBABILITY = 0.60


VALID_DIRECTIONS = {
    "BUY",
    "SELL",
    "HOLD",
    "NO_TRADE",
}


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def run_risk_agent(
    state: dict,
) -> dict:

    # --------------------------------------------------------------
    # Read specialist results.
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

    # --------------------------------------------------------------
    # Extract directions.
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

    valid_opinions = [
        opinion
        for opinion in opinions
        if opinion in VALID_DIRECTIONS
    ]

    # --------------------------------------------------------------
    # Count directional opinions.
    #
    # HOLD and NO_TRADE do not count as BUY or SELL votes,
    # but they remain part of the total agreement calculation.
    # --------------------------------------------------------------

    buy_count = valid_opinions.count(
        "BUY"
    )

    sell_count = valid_opinions.count(
        "SELL"
    )

    total_opinions = len(
        valid_opinions
    )

    # --------------------------------------------------------------
    # Determine dominant direction.
    # --------------------------------------------------------------

    if buy_count > sell_count:

        dominant_direction = "BUY"
        dominant_count = buy_count

    elif sell_count > buy_count:

        dominant_direction = "SELL"
        dominant_count = sell_count

    else:

        dominant_direction = "HOLD"
        dominant_count = 0

    # --------------------------------------------------------------
    # Specialist agreement.
    #
    # Example:
    #
    # BUY / BUY / BUY       = 1.00
    # BUY / BUY / SELL      = 0.67
    # BUY / SELL / NO_TRADE = 0.33
    # --------------------------------------------------------------

    agreement = (
        dominant_count / total_opinions
        if total_opinions > 0
        else 0.0
    )

    # --------------------------------------------------------------
    # Quant information.
    # --------------------------------------------------------------

    quant_probability = _safe_float(
        quant.get("probability")
    )

    quant_model_agreement = _safe_float(
        quant.get("model_agreement")
    )

    quant_probabilities = (
        quant.get(
            "probabilities",
            {},
        )
        or {}
    )

    # --------------------------------------------------------------
    # Find the Quant probability for the dominant direction.
    #
    # This is more useful than simply looking at the predicted
    # direction.
    # --------------------------------------------------------------

    dominant_quant_probability = 0.0

    if dominant_direction in {
        "BUY",
        "SELL",
    }:

        dominant_quant_probability = (
            _safe_float(
                quant_probabilities.get(
                    dominant_direction,
                    0.0,
                )
            )
        )

        # Backward compatibility with the simpler
        # QuantPrediction format.
        if (
            dominant_quant_probability == 0.0
            and quant_direction == dominant_direction
        ):
            dominant_quant_probability = (
                quant_probability
            )

    # --------------------------------------------------------------
    # Quant alignment.
    # --------------------------------------------------------------

    quant_supports_direction = (
        dominant_direction in {
            "BUY",
            "SELL",
        }
        and quant_direction
        == dominant_direction
    )

    quant_opposes_direction = (
        dominant_direction in {
            "BUY",
            "SELL",
        }
        and quant_direction in {
            "BUY",
            "SELL",
        }
        and quant_direction
        != dominant_direction
    )

    # --------------------------------------------------------------
    # Determine whether the Quant Agent provides strong support.
    #
    # The bar is QUANT_PROBABILITY_THRESHOLD (default 0.50, validated on
    # EURUSD 15m): 0.60 admitted ~0.7 candidates/day with a negative net,
    # while 0.50 admitted ~5.9/day with the only profitable net. Majority
    # logic below is unchanged.
    # --------------------------------------------------------------

    quant_bar = quant_threshold()

    quant_has_strong_confidence = (
        dominant_quant_probability
        >= quant_bar
    )

    # --------------------------------------------------------------
    # Initial approval.
    #
    # We require a directional majority from the agents.
    # With three agents this normally means at least 2 agreeing.
    # --------------------------------------------------------------

    approved = (
        dominant_direction
        in {
            "BUY",
            "SELL",
        }
        and dominant_count >= 2
        and total_opinions >= 3
    )

    # --------------------------------------------------------------
    # A strong opposing Quant signal overrides the majority.
    #
    # Example:
    #
    # Technical    BUY
    # Fundamental BUY
    # Quant        SELL 75%
    #
    # The Risk Agent should not blindly approve that trade.
    # --------------------------------------------------------------

    if (
        approved
        and quant_opposes_direction
        and quant_has_strong_confidence
    ):

        approved = False

    # --------------------------------------------------------------
    # Risk classification.
    # --------------------------------------------------------------

    if not approved:

        risk_level = "HIGH"

    elif (
        agreement >= 0.67
        and quant_supports_direction
        and quant_has_strong_confidence
        and quant_model_agreement >= 0.50
    ):

        risk_level = "LOW"

    else:

        risk_level = "MEDIUM"

    # --------------------------------------------------------------
    # Current market price and ATR.
    #
    # Technical Agent currently supplies these values.
    # --------------------------------------------------------------

    current_price = _safe_float(
        technical.get(
            "current_price"
        ),
        default=0.0,
    )

    atr = _safe_float(
        technical.get(
            "atr"
        ),
        default=0.0,
    )

    # --------------------------------------------------------------
    # Trade parameters.
    # --------------------------------------------------------------

    entry_price = None
    stop_loss = None
    take_profit = None
    risk_reward = None

    if (
        approved
        and dominant_direction
        in {
            "BUY",
            "SELL",
        }
        and current_price > 0
        and atr > 0
    ):

        risk_distance = (
            atr
            * STOP_LOSS_ATR_MULTIPLIER
        )

        reward_distance = (
            atr
            * TAKE_PROFIT_ATR_MULTIPLIER
        )

        entry_price = current_price

        if dominant_direction == "BUY":

            stop_loss = (
                current_price
                - risk_distance
            )

            take_profit = (
                current_price
                + reward_distance
            )

        else:

            stop_loss = (
                current_price
                + risk_distance
            )

            take_profit = (
                current_price
                - reward_distance
            )

        risk_reward = (
            reward_distance
            / risk_distance
        )

    # --------------------------------------------------------------
    # Build an explanation for downstream agents/UI.
    # --------------------------------------------------------------

    reason_parts = [
        "Risk assessment based on "
        "Technical, Fundamental and "
        "Quant specialist outputs."
    ]

    reason_parts.append(
        f"Agent agreement: {agreement:.2%}."
    )

    reason_parts.append(
        f"Quant probability for "
        f"{dominant_direction}: "
        f"{dominant_quant_probability:.2%}."
    )

    reason_parts.append(
        f"Quant model agreement: "
        f"{quant_model_agreement:.2%}."
    )

    if quant_opposes_direction:

        reason_parts.append(
            "Quant direction opposes the "
            "dominant specialist direction."
        )

    if not approved:

        reason_parts.append(
            "Trade was not approved by "
            "the Risk Agent."
        )

    # --------------------------------------------------------------
    # Return the graph state update.
    # --------------------------------------------------------------

    return {
        "risk_assessment": {

            "risk_level": risk_level,

            "approved": approved,

            "agreement": agreement,

            "reason": " ".join(
                reason_parts
            ),

            "entry_price": entry_price,

            "stop_loss": stop_loss,

            "take_profit": take_profit,

            "risk_reward": risk_reward,

            # Additional information useful for
            # React/UI/debugging.

            "quant_probability": (
                dominant_quant_probability
            ),

            "quant_model_agreement": (
                quant_model_agreement
            ),

            "dominant_direction": (
                dominant_direction
            ),
        }
    }
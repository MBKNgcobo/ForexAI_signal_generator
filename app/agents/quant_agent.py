from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.ensemble_quant_model import (
    EnsembleQuantModel,
)

from app.models.features import (
    FEATURE_COLUMNS,
    build_features,
)

from app.models.sklearn_quant_model import (
    SklearnQuantModel,
)

from app.models.targets import CLASS_NAMES



# ------------------------------------------------------------------
# Load trained models.
#
# These models were trained using the larger historical dataset.
# ------------------------------------------------------------------

random_forest_model = SklearnQuantModel(
    model_path=(
        "models/"
        "random_forest_full.joblib"
    ),
    model_name="random_forest",
)


xgboost_model = SklearnQuantModel(
    model_path=(
        "models/"
        "xgboost_full.joblib"
    ),
    model_name="xgboost",
)


# ------------------------------------------------------------------
# Create the ensemble.
#
# Current application weights:
#
# Random Forest = 50%
# XGBoost       = 50%
#
# These weights are a working configuration.
# They are not being treated as an optimized trading rule.
# ------------------------------------------------------------------

quant_model = EnsembleQuantModel(
    models=[
        random_forest_model,
        xgboost_model,
    ],
    model_weights={
        "random_forest": 0.5,
        "xgboost": 0.5,
    },
)


def _extract_market_dataframe(
    market_data: Any,
) -> pd.DataFrame:
    """
    Convert the market data supplied by LangGraph
    into a pandas DataFrame.

    The current application may provide:

        list[dict]

    a MarketData object with:

        .candles

    or a dictionary containing:

        {"candles": [...]}

    Expected candle fields:

        datetime
        open
        high
        low
        close
        volume
    """

    if market_data is None:

        raise ValueError(
            "Quant Agent received no market data."
        )

    # --------------------------------------------------------------
    # Current graph format:
    #
    # market_data = list[dict]
    # --------------------------------------------------------------

    if isinstance(
        market_data,
        list,
    ):

        candles = market_data

    # --------------------------------------------------------------
    # Compatibility with MarketData objects.
    # --------------------------------------------------------------

    elif hasattr(
        market_data,
        "candles",
    ):

        candles = market_data.candles

    # --------------------------------------------------------------
    # Compatibility with dictionary-based data.
    # --------------------------------------------------------------

    elif isinstance(
        market_data,
        dict,
    ):

        candles = market_data.get(
            "candles",
            [],
        )

    else:

        raise ValueError(
            "Unsupported market data format: "
            f"{type(market_data).__name__}"
        )

    if not candles:

        raise ValueError(
            "Quant Agent received an empty "
            "market data set."
        )

    # --------------------------------------------------------------
    # Convert candles into dictionaries.
    # --------------------------------------------------------------

    rows = []

    for candle in candles:

        if isinstance(
            candle,
            dict,
        ):

            row = candle.copy()

        elif hasattr(
            candle,
            "model_dump",
        ):

            row = candle.model_dump()

        elif hasattr(
            candle,
            "dict",
        ):

            row = candle.dict()

        else:

            row = {
                "datetime": getattr(
                    candle,
                    "datetime",
                    getattr(
                        candle,
                        "timestamp",
                        None,
                    ),
                ),

                "open": getattr(
                    candle,
                    "open",
                    None,
                ),

                "high": getattr(
                    candle,
                    "high",
                    None,
                ),

                "low": getattr(
                    candle,
                    "low",
                    None,
                ),

                "close": getattr(
                    candle,
                    "close",
                    None,
                ),

                "volume": getattr(
                    candle,
                    "volume",
                    0.0,
                ),
            }

        rows.append(row)

    df = pd.DataFrame(
        rows
    )

    # --------------------------------------------------------------
    # Normalize timestamp naming.
    # --------------------------------------------------------------

    if (
        "datetime" not in df.columns
        and "timestamp" in df.columns
    ):

        df["datetime"] = df[
            "timestamp"
        ]

    # --------------------------------------------------------------
    # Spot FX may not provide exchange volume.
    # --------------------------------------------------------------

    if "volume" not in df.columns:

        df["volume"] = 0.0

    # --------------------------------------------------------------
    # Required market fields.
    # --------------------------------------------------------------

    required_columns = [
        "datetime",
        "open",
        "high",
        "low",
        "close",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Market data is missing required "
            f"columns: {missing_columns}"
        )

    # --------------------------------------------------------------
    # Convert data types.
    # --------------------------------------------------------------

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # --------------------------------------------------------------
    # Clean market data.
    # --------------------------------------------------------------

    df = (
        df
        .dropna(
            subset=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        )
        .drop_duplicates(
            subset="datetime"
        )
        .sort_values(
            "datetime"
        )
        .reset_index(
            drop=True
        )
    )

    if df.empty:

        raise ValueError(
            "No valid market candles remain "
            "after cleaning."
        )

    return df


def _create_quant_prediction(
    market_data: Any,
):
    """
    Build the ML features and generate an ensemble
    prediction using the most recent valid candle.
    """

    # --------------------------------------------------------------
    # Convert market data into DataFrame.
    # --------------------------------------------------------------

    df = _extract_market_dataframe(
        market_data
    )

    # --------------------------------------------------------------
    # Build the same features used during model training.
    # --------------------------------------------------------------

    featured_df = build_features(
        df
    )

    # --------------------------------------------------------------
    # Ensure every trained model feature exists.
    # --------------------------------------------------------------

    missing_features = [
        feature
        for feature in FEATURE_COLUMNS
        if feature not in featured_df.columns
    ]

    if missing_features:

        raise ValueError(
            "Quant Agent is missing required "
            f"features: {missing_features}"
        )

    # --------------------------------------------------------------
    # Keep only rows where every required feature
    # has a valid value.
    # --------------------------------------------------------------

    valid_features = (
        featured_df
        .dropna(
            subset=FEATURE_COLUMNS
        )
        .reset_index(
            drop=True
        )
    )

    if valid_features.empty:

        raise ValueError(
            "Not enough valid market data to "
            "calculate Quant Agent features."
        )

    # --------------------------------------------------------------
    # Use the most recent valid feature row
    # for the live prediction.
    # --------------------------------------------------------------

    latest_features = (
        valid_features[
            FEATURE_COLUMNS
        ]
        .tail(1)
    )

    # --------------------------------------------------------------
    # Run Random Forest + XGBoost ensemble.
    # --------------------------------------------------------------

    prediction = quant_model.predict(
        latest_features
    )

    return prediction


def run_quant_agent(
    state: dict,
) -> dict:
    """
    LangGraph node for the Quant Agent.

    Reads:

        state["market_data"]

    Writes:

        state["quant_prediction"]
    """

    # --------------------------------------------------------------
    # Read market data from graph state.
    # --------------------------------------------------------------

    market_data = state.get(
        "market_data"
    )

    if market_data is None:

        raise ValueError(
            "Quant Agent requires "
            "'market_data' in graph state."
        )

    try:

        prediction = (
            _create_quant_prediction(
                market_data
            )
        )

    except Exception as exc:

        # ----------------------------------------------------------
        # Fail safely.
        #
        # A model failure must never become a BUY or SELL signal.
        # ----------------------------------------------------------

        print(
            "Quant Agent error: "
            f"{type(exc).__name__}: {exc}"
        )

        return {
            "quant_prediction": {
                "direction": "NO_TRADE",

                "probability": 0.0,

                # Required by the existing
                # Python → C# response contract.
                "confidence": 0.0,

                "model": "ensemble",

                "model_agreement": 0.0,

                "probabilities": {
                    "SELL": 0.0,
                    "NO_TRADE": 1.0,
                    "BUY": 0.0,
                },

                "summary": (
                    "Quant analysis could not be "
                    "completed. "
                    f"Error: {exc}"
                ),
            }
        }

    # --------------------------------------------------------------
    # Safely extract ensemble probabilities.
    # --------------------------------------------------------------

    probabilities = (
        prediction.probabilities
        or {}
    )

    # --------------------------------------------------------------
    # Return the successful Quant prediction.
    # --------------------------------------------------------------

    return {
        "quant_prediction": {

            "direction": (
                prediction.direction
            ),

            # ML terminology
            "probability": (
                prediction.probability
            ),

            # Existing ForexAI response contract
            "confidence": (
                prediction.probability
            ),

            "model": (
                prediction.model_name
            ),

            "model_agreement": (
                prediction.model_agreement
            ),

            "probabilities": {

                "SELL": probabilities.get(
                    "SELL",
                    0.0,
                ),

                "NO_TRADE": probabilities.get(
                    "NO_TRADE",
                    0.0,
                ),

                "BUY": probabilities.get(
                    "BUY",
                    0.0,
                ),
            },

            "summary": (
                "Quant ensemble prediction: "
                f"{prediction.direction} "
                f"with confidence "
                f"{prediction.probability:.2%}."
            ),
        }
    }
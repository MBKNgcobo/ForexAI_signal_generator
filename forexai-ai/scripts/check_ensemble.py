import pandas as pd

from app.models.ensemble_quant_model import (
    EnsembleQuantModel,
)
from app.models.sklearn_quant_model import (
    SklearnQuantModel,
)


FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_5",
    "return_10",

    "price_vs_ema20",
    "price_vs_ema50",
    "price_vs_ema200",

    "ema20_above_ema50",
    "ema50_above_ema200",

    "rsi_14",

    "macd",
    "macd_signal",
    "macd_histogram",

    "atr_percentage",
    "rolling_volatility_20",

    "candle_range_percentage",
    "body_percentage_of_price",
    "upper_wick_percentage",
    "lower_wick_percentage",

    "volume_change",
    "volume_ma_20",
]


DATASET_FILE = (
    "data/historical/"
    "EURUSD_15m_full_model_dataset.csv"
)


def main():

    df = pd.read_csv(
        DATASET_FILE
    )

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    # Use the final row only for this
    # model-interface test.

    latest = df.tail(1)

    features = latest[
        FEATURE_COLUMNS
    ]

    random_forest = (
        SklearnQuantModel(
            model_path=(
                "models/"
                "random_forest_full.joblib"
            ),
            model_name="random_forest",
        )
    )

    xgboost = (
        SklearnQuantModel(
            model_path=(
                "models/"
                "xgboost_full.joblib"
            ),
            model_name="xgboost",
        )
    )

    ensemble = EnsembleQuantModel(
        models=[
            random_forest,
            xgboost,
        ],
        model_weights={
            "random_forest": 0.5,
            "xgboost": 0.5,
        },
    )

    prediction = ensemble.predict(
        features
    )

    print()
    print(
        "=" * 60
    )

    print(
        "FOREXAI ENSEMBLE TEST"
    )

    print(
        "=" * 60
    )

    print(
        f"Direction: "
        f"{prediction.direction}"
    )

    print(
        f"Probability: "
        f"{prediction.probability:.4f}"
    )

    print(
        f"Model: "
        f"{prediction.model_name}"
    )

    print(
        f"Agreement: "
        f"{prediction.model_agreement:.2%}"
    )

    print()
    print(
        "Probabilities:"
    )

    for direction, probability in (
        prediction.probabilities or {}
    ).items():

        print(
            f"{direction:10}: "
            f"{probability:.4f}"
        )


if __name__ == "__main__":
    main()
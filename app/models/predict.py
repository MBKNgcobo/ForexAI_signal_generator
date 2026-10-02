from pathlib import Path

import joblib
import pandas as pd

from app.models.features import FEATURE_COLUMNS
from app.models.targets import CLASS_NAMES


DATASET_FILE = Path(
    "data/historical/EURUSD_15m_full_model_dataset.csv"
)



def load_split_data(
    split: str,
) -> pd.DataFrame:

    df = pd.read_csv(
        DATASET_FILE
    )

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    df = (
        df.sort_values("datetime")
        .reset_index(drop=True)
    )

    train_end = int(
        len(df) * 0.70
    )

    validation_end = int(
        len(df) * 0.85
    )

    if split == "train":

        return df.iloc[
            :train_end
        ].copy()

    if split == "validation":

        return df.iloc[
            train_end:validation_end
        ].copy()

    if split == "test":

        return df.iloc[
            validation_end:
        ].copy()

    raise ValueError(
        "split must be "
        "'train', 'validation', "
        "or 'test'"
    )


def generate_predictions(
    split: str,
    model_file: str,
    output_file: str,
) -> None:

    print(
        f"Loading {split} data..."
    )

    df = load_split_data(
        split
    )

    print(
        f"Rows: {len(df)}"
    )

    x = df[
        FEATURE_COLUMNS
    ]

    print(
        f"Loading model: "
        f"{model_file}"
    )

    model = joblib.load(
        model_file
    )

    predictions = model.predict(
        x
    )

    probabilities = (
        model.predict_proba(x)
    )

    df["predicted_class"] = (
        predictions
    )

    df["predicted_direction"] = (
        df["predicted_class"]
        .map(CLASS_NAMES)
    )

    df["sell_probability"] = (
        probabilities[:, 0]
    )

    df["no_trade_probability"] = (
        probabilities[:, 1]
    )

    df["buy_probability"] = (
        probabilities[:, 2]
    )

    output_path = Path(
        output_file
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Saved predictions to: "
        f"{output_path}"
    )

    print(
        "\nPrediction distribution:"
    )

    print(
        df[
            "predicted_direction"
        ]
        .value_counts()
    )

    print(
        "\nAverage probabilities:"
    )

    print(
        df[
            [
                "sell_probability",
                "no_trade_probability",
                "buy_probability",
            ]
        ].mean()
    )


def main():

    generate_predictions(
        split="validation",
        model_file=(
            "models/"
            "xgboost_full.joblib"
        ),
        output_file=(
            "data/historical/"
            "EURUSD_15m_full_"
            "xgboost_validation_predictions.csv"
        ),
    )

if __name__ == "__main__":
    main()
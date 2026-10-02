from pathlib import Path

import pandas as pd

from app.models.features import (
    FEATURE_COLUMNS,
    build_features,
)
from app.models.targets import create_trading_target


INPUT_FILE = Path(
    "data/historical/EURUSD_15m_full.csv"
)

OUTPUT_FILE = Path(
    "data/historical/EURUSD_15m_full_model_dataset.csv"
)



def main():

    print("Loading historical data...")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True,
    )

    df = (
        df.sort_values("datetime")
        .drop_duplicates(
            subset="datetime"
        )
        .reset_index(drop=True)
    )

    print(
        f"Raw rows: {len(df)}"
    )

    print(
        f"Start: {df['datetime'].min()}"
    )

    print(
        f"End: {df['datetime'].max()}"
    )

    # ---------------------------------------------------------
    # Feature engineering
    # ---------------------------------------------------------

    print(
        "\nBuilding features..."
    )

    df = build_features(df)

    print(
        "Features created."
    )

    # ---------------------------------------------------------
    # Target engineering
    # ---------------------------------------------------------

    print(
        "\nCreating trading targets..."
    )

    df = create_trading_target(
        df,
        horizon=12,
        take_profit_atr=1.5,
        stop_loss_atr=1.0,
    )

    print(
        "Targets created."
    )

    # ---------------------------------------------------------
    # Validate feature columns
    # ---------------------------------------------------------

    missing_features = [
        column
        for column in FEATURE_COLUMNS
        if column not in df.columns
    ]

    if missing_features:

        raise ValueError(
            "Missing feature columns: "
            f"{missing_features}"
        )

    # ---------------------------------------------------------
    # Check missing values before cleanup
    # ---------------------------------------------------------

    print(
        "\nMissing values before cleanup:"
    )

    print(
        df[
            FEATURE_COLUMNS + ["target"]
        ]
        .isna()
        .sum()
    )

    # ---------------------------------------------------------
    # Remove incomplete rows
    # ---------------------------------------------------------

    df = (
        df.dropna(
            subset=FEATURE_COLUMNS + ["target"]
        )
        .reset_index(drop=True)
    )

    print(
        "\nRows after removing incomplete rows:"
        f" {len(df)}"
    )

    # ---------------------------------------------------------
    # Target distribution
    # ---------------------------------------------------------

    print(
        "\n========== TARGET DISTRIBUTION =========="
    )

    target_counts = (
        df["target"]
        .value_counts()
        .sort_index()
    )

    target_proportions = (
        df["target"]
        .value_counts(
            normalize=True
        )
        .sort_index()
    )

    labels = {
        -1.0: "SELL",
        0.0: "NO_TRADE",
        1.0: "BUY",
    }

    for target, count in target_counts.items():

        label = labels.get(
            target,
            str(target),
        )

        percentage = (
            target_proportions[target]
            * 100
        )

        print(
            f"{label:10} "
            f"{count:6} "
            f"({percentage:6.2f}%)"
        )

    # ---------------------------------------------------------
    # Save dataset
    # ---------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        f"\nSaved dataset to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBClassifier

from app.models.features import FEATURE_COLUMNS


DATASET_FILE = Path(
    "data/historical/EURUSD_15m_full_model_dataset.csv"
)

MODEL_DIRECTORY = Path("models")



def load_dataset() -> pd.DataFrame:

    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_FILE}"
        )

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

    return df


def split_dataset(
    df: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:

    train_end = int(
        len(df) * 0.70
    )

    validation_end = int(
        len(df) * 0.85
    )

    train = df.iloc[
        :train_end
    ].copy()

    validation = df.iloc[
        train_end:validation_end
    ].copy()

    test = df.iloc[
        validation_end:
    ].copy()

    return (
        train,
        validation,
        test,
    )


def prepare_xy(
    df: pd.DataFrame,
):
    x = df[FEATURE_COLUMNS].copy()

    y = df["target"].map(
        {
            -1.0: 0,
            0.0: 1,
            1.0: 2,
        }
    )

    return x, y


def print_split_distribution(
    name: str,
    df: pd.DataFrame,
) -> None:

    print()
    print(
        f"========== {name} TARGET DISTRIBUTION =========="
    )

    counts = (
        df["target"]
        .value_counts()
        .sort_index()
    )

    proportions = (
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

    for target, count in counts.items():

        label = labels.get(
            target,
            str(target),
        )

        percentage = (
            proportions[target]
            * 100
        )

        print(
            f"{label:10} "
            f"{count:6} "
            f"({percentage:6.2f}%)"
        )


def evaluate_model(
    name: str,
    model,
    x_test: pd.DataFrame,
    y_test,
):

    predictions = model.predict(
        x_test
    )

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    print()
    print(
        "=" * 60
    )

    print(name)

    print(
        "=" * 60
    )

    print(
        f"Accuracy: {accuracy:.4f}"
    )

    print(
        "\nConfusion Matrix:"
    )

    print(
        confusion_matrix(
            y_test,
            predictions,
        )
    )

    print(
        "\nClassification Report:"
    )

    print(
        classification_report(
            y_test,
            predictions,
            target_names=[
                "SELL",
                "NO_TRADE",
                "BUY",
            ],
            zero_division=0,
        )
    )

    return predictions


def main():

    print(
        "Loading dataset..."
    )

    df = load_dataset()

    print(
        f"Rows: {len(df)}"
    )

    print(
        f"Start: {df['datetime'].min()}"
    )

    print(
        f"End: {df['datetime'].max()}"
    )

    print(
        "\nSplitting chronologically..."
    )

    (
        train,
        validation,
        test,
    ) = split_dataset(df)

    print_split_distribution(
        "TRAIN",
        train,
    )

    print_split_distribution(
        "VALIDATION",
        validation,
    )

    print_split_distribution(
        "TEST",
        test,
    )

    print()

    print(
        f"Training rows:    {len(train)}"
    )

    print(
        f"Validation rows: {len(validation)}"
    )

    print(
        f"Test rows:       {len(test)}"
    )

    x_train, y_train = prepare_xy(
        train
    )

    x_validation, y_validation = prepare_xy(
        validation
    )

    x_test, y_test = prepare_xy(
        test
    )

    print()
    print(
        "Training models..."
    )

    models = {

        "Logistic Regression":
            Pipeline(
                [
                    (
                        "scaler",
                        StandardScaler(),
                    ),
                    (
                        "classifier",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=42,
                        ),
                    ),
                ]
            ),

        "Random Forest":
            RandomForestClassifier(
                n_estimators=300,
                max_depth=12,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),

        "XGBoost":
            XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                objective="multi:softprob",
                num_class=3,
                eval_metric="mlogloss",
                random_state=42,
            ),
    }

    MODEL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name, model in models.items():

        print(
            f"\nTraining {name}..."
        )

        model.fit(
            x_train,
            y_train,
        )

        evaluate_model(
            name,
            model,
            x_test,
            y_test,
        )

        filename = (
            name.lower()
            .replace(" ", "_")
            + "_full.joblib"
        )

        output_path = (
            MODEL_DIRECTORY / filename
        )

        joblib.dump(
            model,
            output_path,
        )

        print(
            f"Saved model: {output_path}"
        )


if __name__ == "__main__":
    main()
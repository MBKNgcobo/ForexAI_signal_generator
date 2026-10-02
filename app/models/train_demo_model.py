from pathlib import Path

import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


def create_dataset():
    """
    Creates a small synthetic dataset for architecture testing.

    This is NOT a trading model suitable for real trading.
    """

    X = [
        [0.001, 0.80, 0.002],
        [0.002, 0.85, 0.003],
        [0.003, 0.90, 0.004],
        [-0.001, 0.30, 0.002],
        [-0.002, 0.25, 0.003],
        [-0.003, 0.20, 0.004],
        [0.0015, 0.75, 0.0025],
        [-0.0015, 0.35, 0.0025],
        [0.0025, 0.88, 0.0035],
        [-0.0025, 0.22, 0.0035],
    ]

    y = [
        1,
        1,
        1,
        0,
        0,
        0,
        1,
        0,
        1,
        0,
    ]

    return X, y


def main():

    X, y = create_dataset()

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
        )
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
    )

    predictions = model.predict(
        X_test
    )

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    print(
        f"Demo model accuracy: {accuracy:.2f}"
    )

    output_path = Path(
        "model_artifacts/"
        "eurusd_demo_model.joblib"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        model,
        output_path,
    )

    print(
        f"Model saved to: {output_path}"
    )


if __name__ == "__main__":
    main()
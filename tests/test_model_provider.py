from pathlib import Path

from app.models.sklearn_model import (
    SklearnQuantModel,
)


def test_sklearn_model_can_load():

    model_path = Path(
        "model_artifacts/"
        "eurusd_demo_model.joblib"
    )

    model = SklearnQuantModel(
        model_path=str(model_path),
        model_name="EURUSD-Demo",
        model_version="1.0.0",
    )

    result = model.predict(
        [0.002, 0.85, 0.003]
    )

    assert result["direction"] in {
        "BUY",
        "SELL",
    }

    assert (
        0.0
        <= result["probability"]
        <= 1.0
    )

    assert (
        result["model_name"]
        == "EURUSD-Demo"
    )

    assert (
        result["model_version"]
        == "1.0.0"
    )
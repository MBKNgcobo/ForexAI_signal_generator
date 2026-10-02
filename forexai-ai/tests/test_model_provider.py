from pathlib import Path

import pytest

from app.models.sklearn_model import (
    SklearnQuantModel,
)

# The demo model is a generated artifact (git-ignored). Resolve it relative
# to the package, not the current working directory, so the test works no
# matter where pytest is launched from (repo root, CI, an IDE).
MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "model_artifacts"
    / "eurusd_demo_model.joblib"
)


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason=(
        "demo model artifact not built "
        "(python -m app.models.train_demo_model)"
    ),
)
def test_sklearn_model_can_load():

    model = SklearnQuantModel(
        model_path=str(MODEL_PATH),
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
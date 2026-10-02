from pathlib import Path

import joblib
import pandas as pd

from app.models.quant_model import QuantModel
from app.models.quant_prediction import QuantPrediction
from app.models.targets import CLASS_NAMES

# Model artifacts live in <repo>/models. Resolving them against the process
# working directory meant inference only worked when uvicorn/pytest happened
# to be started from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SklearnQuantModel(QuantModel):

    def __init__(
        self,
        model_path: str,
        model_name: str,
    ):
        candidate = Path(model_path)

        self.model_path = (
            candidate
            if candidate.is_absolute()
            else PROJECT_ROOT / candidate
        )

        self.model_name = model_name

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found: "
                f"{self.model_path}"
            )

        self.model = joblib.load(
            self.model_path
        )

    def predict_probabilities(
        self,
        features: pd.DataFrame,
    ) -> dict[str, float]:

        probabilities = (
            self.model.predict_proba(
                features
            )[0]
        )

        return {
            "SELL": float(probabilities[0]),
            "NO_TRADE": float(probabilities[1]),
            "BUY": float(probabilities[2]),
        }

    def predict(
        self,
        features: pd.DataFrame,
    ) -> QuantPrediction:

        probabilities = (
            self.predict_probabilities(
                features
            )
        )

        direction = max(
            probabilities,
            key=probabilities.get,
        )

        probability = probabilities[
            direction
        ]

        return QuantPrediction(
            direction=direction,
            probability=probability,
            model_name=self.model_name,
            probabilities=probabilities,
        )
from pathlib import Path

import joblib

from app.models.model_provider import QuantModel


class SklearnQuantModel(QuantModel):

    def __init__(
        self,
        model_path: str,
        model_name: str,
        model_version: str,
    ):
        self.model_path = Path(model_path)
        self.model_name = model_name
        self.model_version = model_version

        self.model = joblib.load(
            self.model_path
        )

    def predict(
        self,
        features: list[float],
    ) -> dict:

        prediction = self.model.predict(
            [features]
        )[0]

        probabilities = self.model.predict_proba(
            [features]
        )[0]

        probability = float(
            max(probabilities)
        )

        direction = (
            "BUY"
            if prediction == 1
            else "SELL"
        )

        return {
            "direction": direction,
            "probability": probability,
            "predicted_return": 0.0,
            "model_name": self.model_name,
            "model_version": self.model_version,
        }
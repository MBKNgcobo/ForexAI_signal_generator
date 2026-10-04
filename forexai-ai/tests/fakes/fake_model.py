"""Deterministic stand-in for a trained quantitative model.

The ensemble tests need to control each member's direction and probability
distribution without loading the large (git-ignored) ``.joblib`` artifacts, so
they inject this fake instead of a ``SklearnQuantModel``.
"""

from app.models.quant_model import QuantModel
from app.models.quant_prediction import QuantPrediction
from app.models.targets import DIRECTIONS


class FakeQuantModel(QuantModel):

    def __init__(
        self,
        model_name: str,
        probabilities: dict[str, float],
    ) -> None:
        self.model_name = model_name

        # Always expose every direction so the ensemble can index each one
        # without a KeyError, mirroring what a real model returns.
        self._probabilities = {
            direction: float(probabilities.get(direction, 0.0))
            for direction in DIRECTIONS
        }

    def predict_probabilities(
        self,
        features,
    ) -> dict[str, float]:
        return dict(self._probabilities)

    def predict(
        self,
        features,
    ) -> QuantPrediction:
        direction = max(
            self._probabilities,
            key=self._probabilities.get,
        )

        return QuantPrediction(
            direction=direction,
            probability=self._probabilities[direction],
            model_name=self.model_name,
            probabilities=dict(self._probabilities),
        )

from typing import Sequence

import pandas as pd

from app.models.quant_model import QuantModel
from app.models.quant_prediction import QuantPrediction
from app.models.targets import DIRECTIONS


class EnsembleQuantModel(QuantModel):

    def __init__(
        self,
        models: Sequence[QuantModel],
        model_weights: dict[str, float] | None = None,
    ):
        if not models:
            raise ValueError(
                "At least one model is required."
            )

        self.models = list(models)

        if model_weights is None:

            equal_weight = (
                1.0 / len(self.models)
            )

            self.model_weights = {
                self._get_model_name(model):
                    equal_weight
                for model in self.models
            }

        else:

            self.model_weights = (
                model_weights.copy()
            )

            self._validate_weights()

    def _get_model_name(
        self,
        model: QuantModel,
    ) -> str:

        model_name = getattr(
            model,
            "model_name",
            model.__class__.__name__,
        )

        return str(model_name)

    def _validate_weights(self) -> None:

        model_names = {
            self._get_model_name(model)
            for model in self.models
        }

        missing = (
            model_names
            - set(self.model_weights)
        )

        if missing:

            raise ValueError(
                "Missing weights for models: "
                f"{sorted(missing)}"
            )

        total_weight = sum(
            self.model_weights.values()
        )

        if total_weight <= 0:

            raise ValueError(
                "Model weights must sum "
                "to a positive value."
            )

        # Normalize weights so the caller
        # doesn't have to make them sum to 1.

        for model_name in self.model_weights:

            self.model_weights[model_name] /= (
                total_weight
            )

    def predict_probabilities(
        self,
        features: pd.DataFrame,
    ) -> dict[str, float]:

        ensemble_probabilities = {
            direction: 0.0
            for direction in DIRECTIONS
        }

        total_weight = 0.0

        for model in self.models:

            model_name = (
                self._get_model_name(model)
            )

            weight = (
                self.model_weights[model_name]
            )

            probabilities = (
                model.predict_probabilities(
                    features
                )
            )

            for direction in DIRECTIONS:

                ensemble_probabilities[
                    direction
                ] += (
                    probabilities[direction]
                    * weight
                )

            total_weight += weight

        if total_weight <= 0:

            raise RuntimeError(
                "Total ensemble weight "
                "must be greater than zero."
            )

        return {
            direction:
                probability / total_weight
            for direction, probability
            in ensemble_probabilities.items()
        }

    def _calculate_model_agreement(
        self,
        predictions: list[QuantPrediction],
    ) -> float:

        if not predictions:
            return 0.0

        direction_counts: dict[str, int] = {}

        for prediction in predictions:

            direction = prediction.direction

            direction_counts[direction] = (
                direction_counts.get(
                    direction,
                    0,
                ) + 1
            )

        highest_count = max(
            direction_counts.values()
        )

        return (
            highest_count
            / len(predictions)
        )

    def predict(
        self,
        features: pd.DataFrame,
    ) -> QuantPrediction:

        model_predictions: list[
            QuantPrediction
        ] = []

        for model in self.models:

            prediction = model.predict(
                features
            )

            model_predictions.append(
                prediction
            )

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

        agreement = (
            self._calculate_model_agreement(
                model_predictions
            )
        )

        model_names = ", ".join(
            prediction.model_name
            for prediction in model_predictions
        )

        return QuantPrediction(
            direction=direction,
            probability=probability,
            model_name=(
                f"ensemble({model_names})"
            ),
            probabilities=probabilities,
            model_agreement=agreement,
        )
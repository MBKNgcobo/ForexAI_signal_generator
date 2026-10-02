from abc import ABC, abstractmethod

import pandas as pd

from app.models.quant_prediction import QuantPrediction


class QuantModel(ABC):

    @abstractmethod
    def predict(
        self,
        features: pd.DataFrame,
    ) -> QuantPrediction:
        pass

    def predict_probabilities(
        self,
        features: pd.DataFrame,
    ) -> dict[str, float]:
        raise NotImplementedError(
            "This model does not expose "
            "class probabilities."
        )
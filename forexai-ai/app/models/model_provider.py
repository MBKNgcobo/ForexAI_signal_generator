from abc import ABC, abstractmethod


class QuantModel(ABC):

    @abstractmethod
    def predict(
        self,
        features: list[float],
    ) -> dict:
        pass
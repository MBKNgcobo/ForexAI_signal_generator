from dataclasses import dataclass


@dataclass
class QuantPrediction:
    direction: str
    probability: float
    model_name: str
    probabilities: dict[str, float] | None = None
    model_agreement: float | None = None
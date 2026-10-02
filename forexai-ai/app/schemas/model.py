from pydantic import BaseModel


class ModelPrediction(BaseModel):
    direction: str
    probability: float
    predicted_return: float
    model_name: str
    model_version: str
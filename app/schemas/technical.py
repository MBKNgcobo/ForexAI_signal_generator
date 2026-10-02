from pydantic import BaseModel, Field


class TechnicalAnalysisResponse(BaseModel):
    direction: str = Field(
        description="BUY, SELL, or HOLD"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    summary: str

    reasoning: list[str]
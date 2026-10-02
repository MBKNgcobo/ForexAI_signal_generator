from pydantic import BaseModel, Field


class AgentAnalysis(BaseModel):
    direction: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    summary: str


class RiskAssessment(BaseModel):
    risk_level: str

    approved: bool

    agreement: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    entry_price: float | None = None

    stop_loss: float | None = None

    take_profit: float | None = None

    risk_reward: float | None = None


class FinalDecision(BaseModel):
    direction: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reasoning: str


class AiAnalysisResponse(BaseModel):
    symbol: str
    timeframe: str

    technical_analysis: AgentAnalysis

    fundamental_analysis: AgentAnalysis

    quant_prediction: AgentAnalysis

    risk_assessment: RiskAssessment

    final_decision: FinalDecision
from pydantic import BaseModel, Field


class AgentAnalysis(BaseModel):
    direction: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    # Raw pre-calibration confidence, kept for audit. Optional so older
    # graph states (and third-party callers) still validate.
    raw_confidence: float | None = Field(
        default=None,
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


class Explanation(BaseModel):
    """Auditable "why" behind the signal, built from existing graph state.

    Additive only: older clients ignore it, the dashboard renders it as a
    "Why this signal" block. ``drivers`` names the agreeing specialists,
    ``dissent`` names the opposer (if any) with a reason fragment.
    """

    agreement: float = Field(
        ge=0.0,
        le=1.0,
    )

    quant_agreement: float = Field(
        ge=0.0,
        le=1.0,
    )

    quant_vetoed: bool = False

    drivers: list[str] = Field(default_factory=list)

    dissent: list[str] = Field(default_factory=list)


class AiAnalysisResponse(BaseModel):
    symbol: str
    timeframe: str

    technical_analysis: AgentAnalysis

    fundamental_analysis: AgentAnalysis

    quant_prediction: AgentAnalysis

    risk_assessment: RiskAssessment

    final_decision: FinalDecision

    explanation: Explanation | None = None
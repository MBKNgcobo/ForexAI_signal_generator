using ForexAI.Domain.Enums;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json.Serialization;
using System.Threading.Tasks;


namespace ForexAI.Application.Contracts.Analysis;

public sealed record AiAnalysisResponse(
    string Symbol,
    string Timeframe,

    [property: JsonPropertyName("technical_analysis")]
    AgentAnalysisDto TechnicalAnalysis,

    [property: JsonPropertyName("fundamental_analysis")]
    AgentAnalysisDto FundamentalAnalysis,

    [property: JsonPropertyName("quant_prediction")]
    AgentAnalysisDto QuantPrediction,

    [property: JsonPropertyName("risk_assessment")]
    RiskAssessmentDto RiskAssessment,

    [property: JsonPropertyName("final_decision")]
    FinalDecisionDto FinalDecision
);
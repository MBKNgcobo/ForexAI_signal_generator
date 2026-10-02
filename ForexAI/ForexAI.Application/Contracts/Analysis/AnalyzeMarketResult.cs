using ForexAI.Domain.Enums;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ForexAI.Application.Contracts.Analysis;

public sealed record AnalyzeMarketResult(
    string Symbol,
    string Timeframe,
    AgentAnalysisDto TechnicalAnalysis,
    AgentAnalysisDto FundamentalAnalysis,
    AgentAnalysisDto QuantPrediction,
    RiskAssessmentDto RiskAssessment,
    FinalDecisionDto FinalDecision
);